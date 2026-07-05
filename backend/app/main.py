from fastapi import FastAPI

app = FastAPI(title="Shopping Agent")


@app.get("/health")
async def health():
    return {"status": "ok"}
