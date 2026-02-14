import essentia.standard as es
from collections import Counter

# --- Load + normalize ---
audio = es.MonoLoader(filename="test.wav")()
audio = es.EqualLoudness()(audio)

# --- BPM ---
res = es.RhythmExtractor2013(method="multifeature")(audio)
bpm = float(res[0])

def round_to(x, step):
    return int((x / step) + 0.5) * step

bpm_round_1 = round_to(bpm, 1)   # nearest 1
bpm_round_5 = round_to(bpm, 5)   # nearest 5 (producer-friendly)

# Optional: keep tempo in a "normal producer range"
# If it lands too high, bring it down (halftime); if too low, bring it up (doubletime)
def normalize_bpm(x, low=70, high=180):
    x = float(x)
    while x > high:
        x /= 2.0
    while x < low:
        x *= 2.0
    return x

bpm_final = normalize_bpm(bpm_round_5)
bpm_final = int(bpm_final)  # final integer display

print(f"BPM exact: {bpm:.3f}")
print(f"BPM rounded (1): {bpm_round_1}")
print(f"BPM rounded (5): {bpm_round_5}")
print(f"BPM final (normalized): {bpm_final}")

# --- KEY (multi-profile vote) ---
profiles = ["edma", "krumhansl", "temperley", "bgate", "shaath"]

votes = []
for p in profiles:
    key, scale, strength = es.KeyExtractor(profileType=p)(audio)
    votes.append((key, scale.lower(), float(strength)))
    print(f"[{p}] {key} {scale.lower()}  confidence: {float(strength):.3f}")

# ---- ENSEMBLE DECISION ----

# 1) Decide tonic
tonic_counts = Counter([k for k, s, c in votes])
top_count = max(tonic_counts.values())
top_tonics = [k for k, cnt in tonic_counts.items() if cnt == top_count]

if len(top_tonics) == 1:
    tonic = top_tonics[0]
else:
    # tie-break using summed confidence
    conf_sum = {k: sum(c for kk, ss, c in votes if kk == k) for k in top_tonics}
    tonic = max(conf_sum, key=conf_sum.get)

# 2) Decide mode
minor_score = sum(c for k, s, c in votes if k == tonic and s == "minor")
major_score = sum(c for k, s, c in votes if k == tonic and s == "major")
final_scale = "minor" if minor_score >= major_score else "major"

print("\nFINAL RESULT")
print("BPM:", bpm_final)
print("Key:", tonic, final_scale)
print("minor_score:", minor_score, "major_score:", major_score)