from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai_engine import ask_question, UnsupportedQuestion, UnsafeQuery, LLMUnavailable

app = FastAPI(title="Mini AI BI Assistant")


class Question(BaseModel):
    question: str


@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(body: Question):
    try:
        return ask_question(body.question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnsafeQuery as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnsupportedQuestion as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}")