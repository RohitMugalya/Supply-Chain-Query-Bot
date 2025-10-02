from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import sqlite3

load_dotenv(override=True)

db_name = "supply_chain.db"
conn = sqlite3.connect(db_name)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

with open("system_prompt.txt", "r") as file:
    system_prompt = file.read()

query_executor_tool = {
    "type": "function",
    "function": {
        "name": "query_executor",
        "description": "Execute a query on the database (sqlite3 engine)",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to execute (sqlite3 syntax)"
                }
            },
            "required": ["query"]
        }
    }
}

display_to_me_tool = {
    "type": "function",
    "function": {
        "name": "display_to_me",
        "description": "Displays the last executed READ operation results",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

display_to_user_tool = {
    "type": "function",
    "function": {
        "name": "display_to_user",
        "description": "Displays the last executed READ operation results to the user",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

notify_tool = {
    "type": "function",
    "function": {
        "name": "notify",
        "description": "To notify user the meesage to be conveyed",
        "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "The message to notify the user"}}, "required": ["message"]}
    }
}

tools = [query_executor_tool, display_to_me_tool, display_to_user_tool, notify_tool]


def query_executor(query):
    try:
        cursor.execute(query)
        conn.commit()
        return {"success": True, "error": None}
    except sqlite3.Error as e:
        return {"success": False, "error": repr(e)}


def get_table():
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def notify(message):
    print(message)

def display_to_me():
    return json.dumps(get_table(), indent=2)


def display_to_user():
    print(json.dumps(get_table(), indent=2))


def chat_with_user():
    messages = [{"role": "system", "content": system_prompt}]
    client = OpenAI(api_key=api_key, base_url=base_url)

    waiting_for_tool_result = False

    while True:
        if not waiting_for_tool_result:
            user_input = input("Enter your message (or type 'exit' to quit): ")
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye 👋")
                break
            messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )
        print("Model responded!")

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            for tool_call in choice.message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments or "{}")

                print(f"Tool: {tool_name} with arguments: {tool_args}")
                result = globals()[tool_name](**tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result) if result is not None else "Done"
                })

            waiting_for_tool_result = True

        else:
            if choice.message.content:
                print(f"Assistant:\n{choice.message.content}")
                messages.append({"role": "assistant", "content": choice.message.content})

            waiting_for_tool_result = False

if __name__ == "__main__":
    chat_with_user()
