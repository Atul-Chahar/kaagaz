from fastapi import FastAPI

app = FastAPI(title="Kaagaz")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
