import os
import io
import json
import pandas as pd
import streamlit as st
from typing import List, Dict, Any

from backend import (
    generate_sql_from_nl,
    run_sql_safe,
    is_mutation,
    ensure_limit,
    list_tables,
    table_info,
    foreign_keys,
    row_count,
)

st.set_page_config(page_title="Supply Chain Query Bot", layout="wide")

# --------- Session State ---------
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {nl, sql, confirmed, status, rows}
if "last_rows" not in st.session_state:
    st.session_state.last_rows = None

st.title("Supply Chain Query Bot")

with st.sidebar:
    st.header("Model Settings")
    default_limit = st.number_input("Default LIMIT for SELECT", min_value=10, max_value=100000, value=1000, step=10)
    st.caption("Mutations (INSERT/UPDATE/DELETE/DDL) require confirmation")

# --------- Tabs ---------
chat_tab, schema_tab, history_tab, dashboard_tab = st.tabs(["Chat", "Schema", "History", "Dashboard"])

# --------- Chat Tab ---------
with chat_tab:
    st.subheader("Ask in natural language")
    user_nl = st.text_area("What do you want to know?", placeholder="e.g., Show top 20 products with lowest inventory levels in the last month", height=100)

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Generate SQL", width='stretch', type="primary"):
            if not user_nl.strip():
                st.warning("Please enter a question.")
            else:
                sql, reasoning = generate_sql_from_nl(user_nl)
                st.session_state["pending_sql"] = sql
                st.session_state["pending_nl"] = user_nl
                st.session_state["pending_reasoning"] = reasoning
    with col2:
        if st.button("Clear", width='stretch'):
            for k in ["pending_sql", "pending_nl", "pending_reasoning"]:
                st.session_state.pop(k, None)

    sql = st.session_state.get("pending_sql")
    if sql:
        st.markdown("**Generated SQL**")
        st.code(sql, language="sql")

        # Safety preview & confirmation
        mut = is_mutation(sql)
        if mut:
            st.error("This is a mutating query (INSERT/UPDATE/DELETE/DDL). Confirmation required.")
        else:
            limited_sql = ensure_limit(sql, default_limit=default_limit)
            if limited_sql.strip() != sql.strip():
                st.info("A LIMIT was added for safety.")
                st.code(limited_sql, language="sql")

        run_col1, run_col2 = st.columns([1,1])
        with run_col1:
            if st.button("Run Query", type="primary"):
                if mut:
                    st.warning("Please confirm mutation below before running.")
                else:
                    status, rows = run_sql_safe(sql, default_limit=default_limit)
                    st.session_state.last_rows = rows
                    st.success(status)
                    if rows is not None:
                        df = pd.DataFrame(rows)
                        st.dataframe(df, width='stretch')
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button("Download CSV", data=csv, file_name="results.csv", mime="text/csv")
                    st.session_state.history.append({
                        "nl": st.session_state.get("pending_nl"),
                        "sql": sql,
                        "confirmed": True,
                        "status": status,
                        "rows": len(rows or []),
                    })
        with run_col2:
            confirm_key = "confirm_mutation"
            confirmed = st.checkbox("I confirm executing this mutating query", value=False, key=confirm_key)
            if st.button("Run (Confirmed Mutations)"):
                if mut and not confirmed:
                    st.error("Please check the confirmation box to run mutations.")
                else:
                    status, rows = run_sql_safe(sql, default_limit=default_limit)
                    st.session_state.last_rows = rows
                    if status.startswith("error"):
                        st.error(status)
                    else:
                        st.success(status)
                    if rows is not None:
                        df = pd.DataFrame(rows)
                        st.dataframe(df, width='stretch')
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button("Download CSV", data=csv, file_name="results.csv", mime="text/csv")
                    st.session_state.history.append({
                        "nl": st.session_state.get("pending_nl"),
                        "sql": sql,
                        "confirmed": mut and confirmed or True,
                        "status": status,
                        "rows": len(rows or []),
                    })

# --------- Schema Tab ---------
with schema_tab:
    st.subheader("Database Schema")
    tables = list_tables()
    if not tables:
        st.info("No tables found.")
    else:
        t = st.selectbox("Tables", tables)
        cols = table_info(t)
        fks = foreign_keys(t)
        st.markdown("**Columns**")
        st.dataframe(pd.DataFrame(cols))
        st.markdown("**Foreign Keys**")
        st.dataframe(pd.DataFrame(fks))
        st.markdown("**Row Count**")
        st.write(row_count(t))

# --------- History Tab ---------
with history_tab:
    st.subheader("Session History")
    if not st.session_state.history:
        st.info("No history yet.")
    else:
        dfh = pd.DataFrame(st.session_state.history)
        st.dataframe(dfh, width='stretch')

# --------- Dashboard Tab (KPI skeleton) ---------
with dashboard_tab:
    st.subheader("Supply Chain KPIs (Configure for your schema)")
    st.caption("This section is a starting point. We can wire KPIs once we inspect your schema.")
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.metric("Inventory Turnover", "-", delta=None)
    with kpi_cols[1]:
        st.metric("Fill Rate", "-", delta=None)
    with kpi_cols[2]:
        st.metric("On-time Delivery %", "-", delta=None)
    with kpi_cols[3]:
        st.metric("Avg Lead Time (days)", "-", delta=None)

    st.write("Suggest your table/column names for these KPIs and I'll wire them up.")
