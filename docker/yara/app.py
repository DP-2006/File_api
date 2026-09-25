import os
import time
import tempfile
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import yara

app = FastAPI(title="YARA Scanner API")
RULES_DIR = "/app/rules"
RULES = None

def load_rules():
    global RULES
    filepaths = {}
    for root, _, files in os.walk(RULES_DIR):
        for f in files:
            if f.endswith(('.yar', '.yara')):
                filepaths[os.path.splitext(f)[0]] = os.path.join(root, f)
    try:
        RULES = yara.compile(filepaths=filepaths)
        print(f"Loaded {len(filepaths)} rule files")
    except Exception as e:
        print(f"Error: {e}")
        RULES = None

@app.on_event("startup")
def startup():
    load_rules()

@app.get("/health")
def health():
    return {"status": "ok", "rules_loaded": RULES is not None}

@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    if RULES is None:
        return JSONResponse({"error": "rules not loaded", "score": 0, "threat": False}, status_code=500)
    start = time.time()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        matches = RULES.match(tmp_path)
        results = [{"rule": m.rule, "tags": list(m.tags), "meta": dict(m.meta) if m.meta else {}} for m in matches]
        if results:
            score = min(100, len(results) * 40)
            for r in results:
                if r.get("meta", {}).get("severity") == "critical":
                    score = 100
                    break
            threat = True
        else:
            score, threat = 0, False
        return {"score": score, "threat": threat,
                "details": f"YARA: {', '.join(r['rule'] for r in results)}" if results else "no match",
                "matches": results, "duration_ms": int((time.time() - start) * 1000)}
    finally:
        os.unlink(tmp_path)
