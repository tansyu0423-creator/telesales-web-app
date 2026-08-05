from fastapi import FastAPI

app = FastAPI(title="Telesales Lead Scoring System")

@app.get("/health")
async def health_check():
    return {"status": "ok"}