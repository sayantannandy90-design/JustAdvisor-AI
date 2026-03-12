from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_TOKEN = "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"
API_URL = "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-v0.1"


headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

class CaseInput(BaseModel):
    case_text: str

@app.post("/judge")
def generate_judgment(data: CaseInput):

    payload = {
        "inputs": data.case_text,
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.7
        }
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    result = response.json()

    return {"judgment": result}
