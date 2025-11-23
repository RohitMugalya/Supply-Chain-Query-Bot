# Supply Chain Query Bot

A natural language interface for querying supply chain data, built with Streamlit, SQLite, and Google Gemini.

The Live Demo of the application [Click Here](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://supply-chain-query-bot.streamlit.app/)


## Overview

The **Supply Chain Query Bot** empowers users to interact with a supply chain database using plain English. Instead of writing complex SQL queries, users can ask questions like "Show top 20 products with lowest inventory" or "List all open purchase orders," and the bot generates, validates, and executes the SQL safely.

## Features

-   **Natural Language to SQL**: Converts English questions into SQLite queries using Google's Gemini model.
-   **Interactive Chat Interface**: A chat-like experience for asking questions and viewing results.
-   **Safety First**:
    -   **Read-Only Default**: Defaults to safe `SELECT` queries.
    -   **Mutation Safeguards**: Detects `INSERT`, `UPDATE`, `DELETE`, and DDL statements, requiring explicit user confirmation before execution.
    -   **Automatic Limits**: Automatically adds `LIMIT` clauses to large queries to prevent overwhelming the UI.
-   **Schema Viewer**: Explore tables, columns, foreign keys, and row counts directly in the app.
-   **Session History**: Tracks all queries, generated SQL, and execution status for the current session.
-   **Dashboard**: A placeholder for key supply chain KPIs (Inventory Turnover, Fill Rate, etc.).
-   **Data Export**: Download query results as CSV.

## Tech Stack

-   **Frontend**: [Streamlit](https://streamlit.io/)
-   **Backend Logic**: Python
-   **AI Model**: [Google Gemini](https://ai.google.dev/) (via `google-generativeai`)
-   **Database**: SQLite
-   **Data Manipulation**: Pandas

## Getting Started

### Prerequisites

-   **Python 3.8+**
-   **Google Gemini API Key**: You need an API key from [Google AI Studio](https://aistudio.google.com/).

### Installation

1.  **Clone the repository** (or download the source code).

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables**:
    Create a `.env` file in the root directory and add your API key:
    ```env
    GEMINI_API_KEY=your_actual_api_key_here
    GEMINI_MODEL=gemini-2.0-flash  # Optional, defaults to gemini-2.0-flash
    SCQB_DB_NAME=supply_chain.db   # Optional, defaults to supply_chain.db
    ```

### Database Initialization

The project includes a script to generate a sample supply chain database with realistic dummy data.

Run the initialization script:
```bash
python init_supply_chain_db.py
```
This will create `supply_chain_new.db`. You may need to rename it to `supply_chain.db` or update your `.env` file to match the generated database name if they differ.

### Running the Application

Start the Streamlit app:
```bash
streamlit run app.py
```

The application will open in your default web browser (usually at `http://localhost:8501`).

## Project Structure

-   `app.py`: Main Streamlit application entry point. Handles UI, session state, and user interaction.
-   `backend.py`: Core logic for:
    -   Database connections and execution (`run_sql_safe`).
    -   Prompt engineering and interaction with Gemini (`generate_sql_from_nl`).
    -   Safety checks (`is_mutation`, `ensure_limit`).
    -   Schema introspection (`list_tables`, `table_info`).
-   `init_supply_chain_db.py`: Script to seed a SQLite database with sample data (Products, Suppliers, Warehouses, Orders, etc.).
-   `system_prompt.txt`: The system instruction used to guide the Gemini model.
-   `requirements.txt`: Python dependencies.
