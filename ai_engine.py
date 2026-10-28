import os
import re
import json
import time
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DB_PATH = "sales.db"
MODELS = ["gemini-3.5-flash", "gemini-3.8-flash"]   # preferred first, fallback second
MAX_ROWS = 200
USE_LLM_SUMMARY = False   # False = 1 Gemini call per question (saves quota)

# Layer 1: block destructive intent in the user's question before calling the LLM
DESTRUCTIVE_INTENT = re.compile(
    r"\b(delete|drop|truncate|insert|update|alter|erase|wipe|modify|remove all)\b",
    re.IGNORECASE,
)

# Layer 2: block anything that is not a single read-only SELECT in the generated SQL
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|truncate)\b",
    re.IGNORECASE,
)

BASE_FILTER = "Status = 'Completed' AND Quantity > 0 AND Unit_price IS NOT NULL"
REVENUE = "SUM(Quantity * Unit_price - Discount_amount)"
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6}

_sql_cache: dict = {}
_client = None


class UnsupportedQuestion(Exception):
    pass


class UnsafeQuery(Exception):
    pass


class LLMUnavailable(Exception):
    pass


# ---------------------------------------------------------------- LLM call
def get_client():
    """Create the Gemini client on first use, so importing this module never needs an API key."""
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=30000),
        )
    return _client


def call_llm(prompt: str, json_mode: bool = False) -> str:
    config = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json" if json_mode else None,
    )
    last_error = None
    for round_no in range(2):
        for model_name in MODELS:
            try:
                response = get_client().models.generate_content(
                    model=model_name, contents=prompt, config=config
                )
                return response.text
            except Exception as e:
                last_error = e
                print(f"[LLM] {model_name} (round {round_no + 1}) failed: "
                      f"{type(e).__name__}: {str(e)[:100]}")
        time.sleep(5)
    raise LLMUnavailable(f"Gemini is unavailable right now: {type(last_error).__name__}")


# ---------------------------------------------------------------- prompt
def get_schema() -> str:
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return "\n".join(r[0] for r in rows)


def build_prompt(question: str) -> str:
    return f"""You convert business questions into SQLite SELECT queries.

DATABASE SCHEMA:
{get_schema()}

RULES:
- The table is named sales.
- Revenue = Quantity * Unit_price - Discount_amount.
- Only count rows where Status = 'Completed' AND Quantity > 0 AND Unit_price IS NOT NULL.
- Order_date is stored as YYYY-MM-DD. Use strftime('%Y-%m', Order_date) for months.
- Data covers 2026-01 to 2026-06. Month names refer to 2026.
- Use only the tables and columns in the schema. Write exactly ONE SELECT statement.
- Always SELECT the computed numeric value(s) you rank or filter by (for example
  SUM(...) AS revenue) together with any name column, and give each column a clear alias.
  For "highest"/"top" questions return the top 3 rows with LIMIT 3 so the comparison is visible.
- If the question cannot be answered from this data (weather, opinions, anything unrelated,
  or any request to modify data), set "supported" to false.

Respond with ONLY a JSON object, no markdown:
{{"supported": true/false, "sql": "SELECT ...", "reason": "short explanation"}}

QUESTION: {question}"""


# ---------------------------------------------------------------- deterministic fallback
def fallback_sql(question: str):
    """Rule-based SQL for the standard question types. Used only when the LLM is unavailable."""
    q = question.lower()
    found = [f"2026-{n:02d}" for k, n in MONTHS.items() if re.search(rf"\b{k}", q)]

    if len(found) >= 2 and any(w in q for w in ("change", "between", "compare", "difference", "vs")):
        months = ", ".join(f"'{m}'" for m in found[:2])
        return (f"SELECT strftime('%Y-%m', Order_date) AS month, {REVENUE} AS revenue "
                f"FROM sales WHERE {BASE_FILTER} AND strftime('%Y-%m', Order_date) IN ({months}) "
                f"GROUP BY month ORDER BY month")
    if "month" in q or "trend" in q:
        return (f"SELECT strftime('%Y-%m', Order_date) AS month, {REVENUE} AS revenue "
                f"FROM sales WHERE {BASE_FILTER} GROUP BY month ORDER BY month")
    if "region" in q:
        return (f"SELECT Region, {REVENUE} AS revenue FROM sales WHERE {BASE_FILTER} "
                f"GROUP BY Region ORDER BY revenue DESC LIMIT 3")
    if "product" in q:
        return (f"SELECT Product, {REVENUE} AS revenue FROM sales WHERE {BASE_FILTER} "
                f"GROUP BY Product ORDER BY revenue DESC LIMIT 3")
    if "total" in q and ("revenue" in q or "sales" in q):
        return f"SELECT {REVENUE} AS total_revenue FROM sales WHERE {BASE_FILTER}"
    return None


# ---------------------------------------------------------------- pipeline steps
def generate_sql(question: str):
    """Returns (sql, source) where source is 'llm', 'cache' or 'fallback'."""
    key = question.lower()
    if key in _sql_cache:
        return _sql_cache[key], "cache"

    try:
        text = call_llm(build_prompt(question), json_mode=True)
    except LLMUnavailable:
        sql = fallback_sql(question)
        if sql is None:
            raise
        return sql, "fallback"

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise UnsupportedQuestion("The AI returned an unreadable response. Please rephrase.")

    if not data.get("supported") or not data.get("sql"):
        raise UnsupportedQuestion(
            data.get("reason") or "This question cannot be answered from the sales data."
        )
    _sql_cache[key] = data["sql"].strip()
    return _sql_cache[key], "llm"


def validate_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";").strip()
    if ";" in sql:
        raise UnsafeQuery("Multiple statements are not allowed.")
    if not sql.lower().startswith(("select", "with")):
        raise UnsafeQuery("Only SELECT queries are allowed.")
    if FORBIDDEN_SQL.search(sql):
        raise UnsafeQuery("Query contains a forbidden keyword.")
    if "--" in sql or "/*" in sql:
        raise UnsafeQuery("SQL comments are not allowed.")
    return sql


def run_query(sql: str):
    # read-only connection: even if validation failed, writes are impossible
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchmany(MAX_ROWS)]
    return rows


def _fmt(v):
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def summarize_rows(rows: list) -> str:
    """Deterministic answer text built straight from the query results (no LLM call)."""
    if not rows:
        return "No matching data was found."
    if len(rows) == 1:
        return "Result: " + ", ".join(f"{k} = {_fmt(v)}" for k, v in rows[0].items())
    first = ", ".join(f"{k} = {_fmt(v)}" for k, v in rows[0].items())
    return f"{len(rows)} rows returned. Top row: {first}. See the table below for all figures."


def explain_result(question: str, sql: str, rows: list) -> str:
    if not USE_LLM_SUMMARY:
        return summarize_rows(rows)
    prompt = f"""Answer the business question in 1-3 sentences using ONLY these query results.
Do not invent numbers. If the results are empty, say no data was found.

QUESTION: {question}
SQL: {sql}
RESULTS: {json.dumps(rows[:50], default=str)}"""
    try:
        return call_llm(prompt).strip()
    except LLMUnavailable:
        return summarize_rows(rows)


def ask_question(question: str) -> dict:
    question = (question or "").strip()
    if not question:
        raise ValueError("Question cannot be empty.")
    if len(question) > 500:
        raise ValueError("Question is too long (max 500 characters).")
    if DESTRUCTIVE_INTENT.search(question):
        raise UnsafeQuery("This assistant is read-only and cannot modify data.")

    raw_sql, source = generate_sql(question)
    sql = validate_sql(raw_sql)
    try:
        rows = run_query(sql)
    except sqlite3.Error as e:
        raise UnsafeQuery(f"Generated query failed to run: {e}")

    return {
        "question": question,
        "answer": explain_result(question, sql, rows),
        "sql": sql,
        "source": source,
        "supporting_data": rows,
    }