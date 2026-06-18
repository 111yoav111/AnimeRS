from fastapi import FastAPI, UploadFile, File
import identifier

app = FastAPI(title="AnimeSearcher")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search")
async def search(image: UploadFile = File(...)):
    image_bytes = await image.read()
    return identifier.identify(image_bytes)
