# markoff_server.py
# FastAPI HTTP adapter for the Markoff Engine
# Exposes: POST /clarify

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Markoff Engine", version="0.1")


# ------------------------------------------------------------
#  REQUEST / RESPONSE MODELS
# ------------------------------------------------------------

class ClarifyRequest(BaseModel):
    text: str
    meta: dict | None = None


class ClarifyResponse(BaseModel):
    engine: str = "markoff"
    score: float
    tags: list[str]
    interpretation: str


# ------------------------------------------------------------
#  INTERNAL PLACEHOLDER LOGIC
#  (Replace with real Markoff engine later)
# ------------------------------------------------------------

def run_markoff_engine(text: str):
    """
    Deterministic placeholder logic.
    Replace with real Markoff Engine logic later.
    """

    # Simple scoring heuristic for now
    length = len(text.strip())
    score = min(1.0, length / 200.0)

    # Fake tags based on simple heuristics
    tags = []
    if "?" in text:
        tags.append("question")
    if "!" in text:
        tags.append("emphasis")
    if length > 120:
        tags.append("long")

    interpretation = f"(markoff_stub) Interpreted input: {text[:120]}..."

    return score, tags, interpretation


# ------------------------------------------------------------
#  ENDPOINT
# ------------------------------------------------------------

@app.post("/clarify", response_model=ClarifyResponse)
def clarify(req: ClarifyRequest):
    score, tags, interpretation = run_markoff_engine(req.text)
    return ClarifyResponse(
        score=score,
        tags=tags,
        interpretation=interpretation
    )


# ------------------------------------------------------------
#  HEALTH CHECK
# ------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "engine": "markoff", "version": "0.1"}
