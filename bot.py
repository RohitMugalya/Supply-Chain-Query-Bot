from dotenv import load_dotenv
import json
from backend import generate_sql_from_nl, run_sql_safe, is_mutation, ensure_limit

load_dotenv(override=True)


def chat_with_user():
    print("Supply Chain Query Bot (Gemini) - type 'exit' to quit")
    while True:
        user_input = input("\nEnter your request: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("Goodbye 👋")
            break

        sql, _reason = generate_sql_from_nl(user_input)
        print("\nGenerated SQL:\n" + sql)

        if is_mutation(sql):
            confirm = input("This query modifies data. Type 'yes' to proceed: ").strip().lower()
            if confirm != "yes":
                print("Skipped execution.")
                continue

        status, rows = run_sql_safe(sql)
        if status.startswith("error"):
            print(status)
            continue

        if rows is None:
            print("Success: mutation executed.")
        else:
            print(f"Returned {len(rows)} row(s).")
            print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    chat_with_user()
