import os
import re
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(override=True)

DB_NAME = os.getenv("SCQB_DB_NAME", "supply_chain.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# ---------- DB Utilities ----------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), DB_NAME))
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(query: str) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(query)
        conn.commit()
        if query.strip().lower().startswith("select"):
            rows = [dict(r) for r in cur.fetchall()]
            return ("ok", rows)
        else:
            return ("ok", None)
    except sqlite3.Error as e:
        return (f"error: {e!r}", None)
    finally:
        conn.close()


def fetchall(cur: sqlite3.Cursor) -> List[Dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def list_tables() -> List[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables


def table_info(table: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    cols = fetchall(cur)
    conn.close()
    return cols


def foreign_keys(table: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA foreign_key_list({table});")
    fks = fetchall(cur)
    conn.close()
    return fks


def row_count(table: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) as c FROM {table};")
        c = cur.fetchone()[0]
        return int(c)
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def schema_summary(limit_per_table: int = 5) -> str:
    summary: List[str] = []
    for t in list_tables():
        cols = table_info(t)
        col_str = ", ".join([f"{c['name']} {c['type']}" for c in cols])
        summary.append(f"TABLE {t} COLUMNS: {col_str}")
    return "\n".join(summary)


# ---------- Safety Helpers ----------

_MUTATION_RE = re.compile(r"^\s*(insert|update|delete|create|drop|alter|replace|truncate)\b", re.IGNORECASE)


def is_mutation(sql: str) -> bool:
    return bool(_MUTATION_RE.match(sql.strip()))


def ensure_limit(sql: str, default_limit: int = 1000) -> str:
    s = sql.strip().rstrip(";")
    if not s.lower().startswith("select"):
        return sql
    if re.search(r"\blimit\b", s, re.IGNORECASE):
        return sql
    return f"{s} LIMIT {default_limit};"


# ---------- Model Utilities ----------

def _gemini_model(system_instruction: Optional[str] = None):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment")
    genai.configure(api_key=GEMINI_API_KEY)
    if system_instruction:
        return genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=system_instruction)
    return genai.GenerativeModel(model_name=GEMINI_MODEL)


def generate_sql_from_nl(nl_request: str, extra_instructions: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns (sql, reasoning). Uses system prompt and asks the model to output a minimal SQL query.
    """
    schema = schema_summary()
    instruction = (
        "You are an expert SQL generator for SQLite. Given a natural-language request and the SQLite schema, "
        "output a single best SQL statement. Do not include explanations or markdown. Do not wrap in backticks. "
        "Prefer safe SELECTs unless the user explicitly requests data modification."
    )
    if extra_instructions:
        instruction += "\n" + extra_instructions

    model = _gemini_model(system_instruction=f"{SYSTEM_PROMPT}\n\n{instruction}")
    generation_config = genai.GenerationConfig(
        temperature=0.1,
        top_p=0.9,
        candidate_count=1,
        response_mime_type="text/plain",
    )

    def _clean(sql_text: str) -> str:
        t = (sql_text or "").strip()
        t = t.strip("`").strip()
        first_line_end = t.find("\n")
        first_token_line = t if first_line_end == -1 else t[:first_line_end]
        lower = first_token_line.strip().lower()
        if lower in {"sql", "sqlite", "mysql", "postgresql", "postgres"}:
            t = t[first_line_end + 1 :] if first_line_end != -1 else ""
        return t.strip()

    def validate_select_sql(sql_text: str) -> Tuple[bool, Optional[str]]:
        s = sql_text.strip().rstrip(";")
        if not s.lower().startswith("select"):
            return True, None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(f"EXPLAIN QUERY PLAN {s}")
            _ = cur.fetchall()
            conn.close()
            return True, None
        except sqlite3.Error as e:
            try:
                conn.close()
            except Exception:
                pass
            return False, str(e)

    base_prompt = (
        f"SQLite schema summary:\n{schema}\n\n"
        f"User request: {nl_request}\n\n"
        f"Return only the SQL query with no commentary."
    )

    attempts = 3
    last_error = None
    for i in range(attempts):
        resp = model.generate_content(base_prompt, generation_config=generation_config)
        sql = _clean(resp.text)
        ok, err = validate_select_sql(sql)
        if ok:
            reasoning = "SQL generated via Gemini and validated against SQLite."
            return sql, reasoning
        # Add feedback and retry
        last_error = err
        base_prompt = (
            f"SQLite schema summary:\n{schema}\n\n"
            f"User request: {nl_request}\n\n"
            f"The previous SQL caused an SQLite error: {err}.\n"
            f"Regenerate a valid SQL that matches the schema. Return only the SQL."
        )

    # If all attempts failed, return the last SQL (uncertain) and include reasoning
    return sql, f"Model attempts exhausted; last validation error: {last_error}"


def run_sql_safe(sql: str, default_limit: int = 1000) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    if is_mutation(sql):
        # Caller must confirm mutations; we simply run if given.
        return execute_query(sql)
    # Ensure limit for SELECTs
    safe_sql = ensure_limit(sql, default_limit=default_limit)
    return execute_query(safe_sql)
