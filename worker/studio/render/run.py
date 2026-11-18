"""Render in a fresh, single-threaded process (safe to fork a worker pool from).

  python -m studio.render.run spec.json   → prints probe JSON on the last line
"""
import json
import sys

from .compose import BeatT, Spec, render_video


def main(path: str) -> None:
    d = json.load(open(path))
    d["beats"] = [BeatT(**b) for b in d["beats"]]
    d["scenes"] = {int(k): v for k, v in d["scenes"].items()}
    d["words"] = [tuple(w) for w in d["words"]]
    print(json.dumps(render_video(Spec(**d))))


if __name__ == "__main__":
    main(sys.argv[1])
