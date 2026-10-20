
from fastapi import FastAPI

app = FastAPI(
    title="DCC Curtailment Prioritizer",
    description="API for distribution-level solar curtailment prioritisation",
    version="0.1.0",
)


@app.get("/")
def home():
    return {
        "message": "DCC Curtailment Prioritizer API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
