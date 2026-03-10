from fastapi import FastAPI

app = FastAPI(title="Zero-Shot RC Car Backend")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
