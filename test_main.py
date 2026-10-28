import json
import pytest
from fastapi.testclient import TestClient

import ai_engine
from ai_engine import LLMUnavailable
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    ai_engine._sql_cache.clear()


@pytest.fixture
def llm_down(monkeypatch):
    def boom(*args, **kwargs):
        raise LLMUnavailable("simulated outage")
    monkeypatch.setattr(ai_engine, "call_llm", boom)


def ask(q):
    return client.post("/ask", json={"question": q})


# ---- valid questions (deterministic path) ----
def test_total_revenue(llm_down):
    r = ask("What is the total revenue?")
    assert r.status_code == 200
    assert r.json()["supporting_data"][0]["total_revenue"] == 1439200


def test_top_product(llm_down):
    r = ask("Which product generated the highest revenue?")
    top = r.json()["supporting_data"][0]
    assert top["Product"] == "Monitor" and top["revenue"] == 473000


def test_top_region(llm_down):
    r = ask("Which region generated the highest sales?")
    top = r.json()["supporting_data"][0]
    assert top["Region"] == "South" and top["revenue"] == 411200


def test_revenue_change_april_may(llm_down):
    r = ask("How did revenue change between April and May?")
    rows = {x["month"]: x["revenue"] for x in r.json()["supporting_data"]}
    assert rows == {"2026-04": 240700, "2026-05": 318500}


# ---- LLM path with a faked reply ----
def test_llm_generated_sql_is_used(monkeypatch):
    fake = json.dumps({"supported": True,
                       "sql": "SELECT COUNT(*) AS n FROM sales", "reason": ""})
    monkeypatch.setattr(ai_engine, "call_llm", lambda *a, **k: fake)
    r = ask("How many transactions are there?")
    assert r.status_code == 200 and r.json()["source"] == "llm"
    assert r.json()["supporting_data"][0]["n"] == 51


# ---- invalid / unsafe requests ----
def test_destructive_question_rejected():
    r = ask("Delete all sales records")
    assert r.status_code == 400


def test_empty_question_rejected():
    assert ask("   ").status_code == 400


def test_unsupported_question_rejected(monkeypatch):
    fake = json.dumps({"supported": False, "sql": "", "reason": "Not about sales data."})
    monkeypatch.setattr(ai_engine, "call_llm", lambda *a, **k: fake)
    assert ask("What's the weather today?").status_code == 422


def test_malicious_sql_from_llm_is_blocked(monkeypatch):
    fake = json.dumps({"supported": True, "sql": "DROP TABLE sales", "reason": ""})
    monkeypatch.setattr(ai_engine, "call_llm", lambda *a, **k: fake)
    assert ask("Show me something").status_code == 400


def test_multiple_statements_blocked():
    with pytest.raises(ai_engine.UnsafeQuery):
        ai_engine.validate_sql("SELECT 1; SELECT 2")


# ---- edge case ----
def test_bad_rows_are_excluded(llm_down):
    # 51 rows loaded, but returned / zero-quantity / missing-price rows must not count
    r = ask("What is the total revenue?")
    assert r.json()["supporting_data"][0]["total_revenue"] == 1439200