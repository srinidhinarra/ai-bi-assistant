import time
from ai_engine import (
    ask_question, UnsupportedQuestion, UnsafeQuery, LLMUnavailable,
)

questions = [
    "What is the total revenue?",
    "Which product generated the highest revenue?",
    "Which region generated the highest sales?",
    "What is the monthly revenue trend?",
    "How did revenue change between April and May?",
    "Delete all sales records",
    "What's the weather today?",
]

for q in questions:
    print("\nQ:", q)
    try:
        result = ask_question(q)
        print("A:", result["answer"])
        print("SQL:", result["sql"])
        print("SOURCE:", result["source"])
        print("DATA:", result["supporting_data"])
    except (UnsupportedQuestion, UnsafeQuery, ValueError, LLMUnavailable) as e:
        print("REJECTED:", e)
    time.sleep(8)