from fastapi import FastAPI
from pydantic import BaseModel
import markoff  # your engine file

app = FastAPI(title="Markov Clarity Engine")

class AnalyzeRequest(BaseModel):
    text: str

@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    # Adjust this call once we inspect markoff.py
    result = markoff.analyze(req.text)
    return result