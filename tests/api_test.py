import httpx
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_PATH = os.path.join(SCRIPT_DIR, "test2.jpeg")  

with open(IMG_PATH, "rb") as f:
    files = {"image": f}        
    resp = httpx.post(
        "https://api.trace.moe/search",
        params={"anilistInfo": ""},
        files=files,
    )

resp.raise_for_status()
data = resp.json()

t = data["result"][0]
time_m = t["from"] / 60
print("title:", t["anilist"]["title"])
print("episode:", t["episode"])
print("from (sec):", t["from"]) 
print(f"min time - {time_m}")
print("similarity:", t["similarity"]) # 0-1, %
