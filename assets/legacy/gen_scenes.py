"""Generate Overthought scene images on RunPod (Flux dev).

Usage:
  python3 pipeline/gen_scenes.py NAME "scene description" [--seed N] [--yellow]

The RunPod API key is injected by the cloud environment's network proxy,
so no key is read from the environment here.

Style rules learned so far:
- Default is monochrome white. Add yellow accents in code (style.scene tint/fill)
  so the character never turns yellow.
- Use --yellow only when the glowing element is hard to add later (e.g. the scribble cloud).
- The output is always 1024x1024, whatever size you ask for.
- Cost is about $0.012 per image.
"""
import argparse, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = "https://api.runpod.ai/v2/black-forest-labs-flux-1-dev/runsync"
BASE = ("classic stick figure made of single thin white lines: circle head, one straight line body, "
        "two line arms, two line legs, on pure black background, flat minimal hand-drawn vector, "
        "{accent}, no shading, no text, no letters, ")
MONO = "monochrome white lines only"
YELLOW = "glowing electric yellow accent"

def generate(name, desc, seed=7, yellow=False):
    prompt = BASE.format(accent=YELLOW if yellow else MONO) + desc
    body = json.dumps({"input": {"prompt": prompt, "num_inference_steps": 28,
                                 "guidance": 3.5, "seed": seed}}).encode()
    req = urllib.request.Request(ENDPOINT, body, {"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=280))
    out = os.path.join(ROOT, "scenes", name + ".jpg")
    urllib.request.urlretrieve(d["output"]["result"], out)
    return out, d["output"].get("cost")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("desc")
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--yellow", action="store_true")
    a = ap.parse_args()
    print(generate(a.name, a.desc, a.seed, a.yellow))
