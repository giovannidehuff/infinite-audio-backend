import os
import uuid
import tempfile
from collections import Counter

import essentia.standard as es
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow your frontend to call this (tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev: allow everything
    allow_credentials=False,      # keep false when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILES = ["edma", "krumhansl", "temperley", "bgate", "shaath"]

def round_to(x, step):
    return int((x / step) + 0.5) * step

def normalize_bpm(x, low=70, high=180):
    x = float(x)
    while x > high:
        x /= 2.0
    while x < low:
        x *= 2.0
    return x

def analyze_file(path: str):
    audio = es.MonoLoader(filename=path)()
    audio = es.EqualLoudness()(audio)

    # BPM
    res = es.RhythmExtractor2013(method="multifeature")(audio)
    bpm_exact = float(res[0])
    bpm_round_5 = round_to(bpm_exact, 5)
    bpm_final = int(normalize_bpm(bpm_round_5))

    # Key votes
    votes = []
    for p in PROFILES:
        key, scale, strength = es.KeyExtractor(profileType=p)(audio)
        votes.append((key, scale.lower(), float(strength)))

    # Tonic vote
    tonic_counts = Counter([k for k, s, c in votes])
    top_count = max(tonic_counts.values())
    top_tonics = [k for k, cnt in tonic_counts.items() if cnt == top_count]

    if len(top_tonics) == 1:
        tonic = top_tonics[0]
    else:
        conf_sum = {k: sum(c for kk, ss, c in votes if kk == k) for k in top_tonics}
        tonic = max(conf_sum, key=conf_sum.get)

    # Mode vote
    minor_score = sum(c for k, s, c in votes if k == tonic and s == "minor")
    major_score = sum(c for k, s, c in votes if k == tonic and s == "major")
    final_scale = "minor" if minor_score >= major_score else "major"

    # Confidence (simple, readable)
    total = minor_score + major_score
    mode_conf = (max(minor_score, major_score) / total) if total > 0 else 0.0

    return {
        "bpm": bpm_final,
        "bpm_exact": round(bpm_exact, 3),
        "key": f"{tonic} {final_scale}",
        "tonic": tonic,
        "scale": final_scale,
        "mode_confidence": round(mode_conf, 3),
        "debug_votes": [
            {"profile": p, "tonic": k, "scale": s, "confidence": round(c, 3)}
            for (k, s, c), p in zip(votes, PROFILES)
        ],
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".wav", ".mp3", ".m4a", ".flac", ".aiff", ".aif"]:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save to temp
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"ia_{uuid.uuid4().hex}{ext}")

    try:
        contents = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        result = analyze_file(tmp_path)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except:
            pass