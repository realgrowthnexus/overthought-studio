"""In-memory stand-ins for Supabase, Claude, RunPod and the voice engine so the real pipeline can run offline."""
from __future__ import annotations

import collections
import copy
import fnmatch
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from studio import config, content, db, images, llm, pipeline, settings, voice
from studio.voice import Word

WORDS_PER_SECOND = 2.1          # Kokoro's measured pace


def _match(row: dict, where: dict | None) -> bool:
    for k, v in (where or {}).items():
        have = row.get(k)
        if isinstance(v, tuple):
            op, val = v
            if op == "in":
                ok = have in val
            elif op == "like":
                ok = have is not None and fnmatch.fnmatch(str(have), str(val))
            elif op in ("gte", "gt", "lte", "lt"):
                ok = have is not None and {"gte": have >= val, "gt": have > val,
                                           "lte": have <= val, "lt": have < val}[op]
            elif op == "neq":
                ok = have != val
            elif op == "is":
                ok = have is None if val == "null" else have == (val == "true")
            elif op == "not.is":
                ok = have is not None if val == "null" else have != (val == "true")
            else:
                raise NotImplementedError(f"fake db filter {op}")
        elif v is None:
            ok = have is None
        else:
            ok = str(have) == str(v) if not isinstance(v, bool) else have is v
        if not ok:
            return False
    return True


@dataclass
class FakeWorld:
    tables: dict[str, list[dict]] = field(default_factory=lambda: collections.defaultdict(list))
    storage: dict[str, bytes] = field(default_factory=dict)
    calls: collections.Counter = field(default_factory=collections.Counter)
    fail_next: dict[str, Exception] = field(default_factory=dict)
    script_factory: object = None          # (ch, idea) -> content.Script
    factcheck_passes: bool = True
    factcheck_minor: tuple = ()

    # ------------------------------------------------------------- db
    def select(self, table, where=None, *, columns="*", order=None, limit=None, single=False):
        rows = [copy.deepcopy(r) for r in self.tables[table] if _match(r, where)]
        if limit:
            rows = rows[:limit]
        return (rows[0] if rows else None) if single else rows

    def insert(self, table, rows, *, upsert=False, on_conflict=None, ignore_duplicates=False):
        out = []
        for r in rows if isinstance(rows, list) else [rows]:
            r = copy.deepcopy(r)
            if upsert and on_conflict:
                hit = next((x for x in self.tables[table] if x.get(on_conflict) == r.get(on_conflict)), None)
                if hit:
                    if not ignore_duplicates:
                        hit.update(r)
                    out.append(copy.deepcopy(hit))
                    continue
            r.setdefault("id", str(uuid.uuid4()))
            r.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            self.tables[table].append(r)
            out.append(copy.deepcopy(r))
        return out

    def update(self, table, where, values):
        out = []
        for r in self.tables[table]:
            if _match(r, where):
                r.update(copy.deepcopy(values))
                out.append(copy.deepcopy(r))
        return out

    def delete(self, table, where):
        self.tables[table] = [r for r in self.tables[table] if not _match(r, where)]

    def rpc(self, fn, args=None, *, idempotent=False):
        if fn == "spend_total":
            return sum(float(r["amount_usd"]) for r in self.tables["spend"])
        raise NotImplementedError(f"fake rpc {fn}")

    def upload(self, bucket, path, data, content_type):
        self.storage[f"{bucket}/{path}"] = bytes(data)
        return path

    def download(self, bucket, path):
        try:
            return self.storage[f"{bucket}/{path}"]
        except KeyError:
            raise db.DBError(f"GET /storage/v1/object/{bucket}/{path} -> 400 not found") from None

    def list_objects(self, bucket, prefix="", limit=1000):
        pre = f"{bucket}/{prefix}"
        return [{"name": k[len(pre):], "id": k} for k in sorted(self.storage) if k.startswith(pre) and "/" not in k[len(pre):]]

    def remove(self, bucket, paths):
        for p in paths:
            self.storage.pop(f"{bucket}/{p}", None)

    # ------------------------------------------------------------- services
    def _maybe_fail(self, service: str) -> None:
        if service in self.fail_next:
            raise self.fail_next.pop(service)

    def structured(self, schema, system, prompt, *, purpose, effort=None, max_tokens=16000, channel_id=None,
                   video_id=None):
        self.calls["claude"] += 1
        self._maybe_fail("anthropic")
        if schema is content.Script:
            return (self.script_factory or clean_script)(), 0.05
        if schema is content.Scorecard:
            return content.Scorecard(hook=9, curiosity_gap=9, viewer_question=8, emotional_connection=8, clarity=9,
                                     pacing=8, accuracy_framing=9, loop=8, originality=8, overall=8.6,
                                     biggest_risk="none", fixes=[]), 0.01
        if schema is content.FactCheck:
            ok = self.factcheck_passes
            return content.FactCheck(claims=[], citations_valid=ok, passes=ok,
                                     required_changes=[] if ok else ["The 25% figure is not in the paper"],
                                     blocking=[] if ok else ["The 25% figure is not in the paper"],
                                     minor=list(self.factcheck_minor), summary="fake"), 0.01
        raise NotImplementedError(schema)

    def research(self, system, prompt, *, purpose, max_searches=8, effort=None, channel_id=None, video_id=None):
        self.calls["claude"] += 1
        self._maybe_fail("anthropic")
        return ("Radvansky, Notre Dame, 2011: walking through doorways increases forgetting.",
                [{"url": "https://doi.org/10.1080/17470218.2011.571267", "title": "Radvansky 2011", "cited_text": ""}],
                0.2)

    def generate(self, description, *, seed=7, figure_prompt=None, channel_id=None, video_id=None):
        self.calls["runpod"] += 1
        self._maybe_fail("runpod")
        im = Image.new("RGB", (1024, 1024), (0, 0, 0))
        d = ImageDraw.Draw(im)
        x = 400 + (seed % 5) * 40
        d.ellipse((x, 260, x + 90, 350), outline=(255, 255, 255), width=6)
        d.line([(x + 45, 350), (x + 45, 650)], fill=(255, 255, 255), width=6)
        d.line([(x + 45, 650), (x - 10, 820)], fill=(255, 255, 255), width=6)
        d.line([(x + 45, 650), (x + 100, 820)], fill=(255, 255, 255), width=6)
        d.line([(x + 45, 430), (x - 40, 540)], fill=(255, 255, 255), width=6)
        return im, 0.01

    def synthesize(self, text, voice_cfg, *, channel_id=None, video_id=None):
        self.calls["voice"] += 1
        self._maybe_fail("voice")
        words, t = [], 0.0
        for w in text.split():
            words.append(Word(w, round(t, 3), round(t + 0.3, 3)))
            t += 1 / WORDS_PER_SECOND
        dur = words[-1].end + 0.7
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "v.mp3"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                            "-t", f"{dur:.2f}", "-q:a", "9", str(p)], check=True)
            return p.read_bytes(), words, 0.0


def _beat(i: int, kind: str, n_scenes: int, words: int = 17) -> content.Beat:
    return content.Beat(kind=kind, narration=" ".join(f"word{i}x{j}" for j in range(words)) + ".",
                        onscreen=[content.TextPart(text="your brain ", kind="ink"),
                                  content.TextPart(text="forgets", kind="key")],
                        scene_id=i % n_scenes, accent="question_mark" if i % 2 else "lightbulb",
                        source_index=0 if kind == "study" else None, flash=kind == "payoff")


KINDS = ["hook", "open_loop", "question", "story", "study", "twist", "story", "fix", "payoff", "loop"]


def clean_script() -> content.Script:
    """10 beats × 17 words = 170 words ≈ 81 s at 2.1 words/s (inside word_range of the seed channel)."""
    return content.Script(
        title="Why doorways make you forget", hook_line="Walking through a door erases your memory",
        hook_style="you-callout", beats=[_beat(i, k, 4) for i, k in enumerate(KINDS)],
        scenes=[content.Scene(id=i, description=f"stick figure scene {i}") for i in range(4)],
        sources=[content.Source(researcher="Radvansky", institution="Notre Dame", year=2011,
                                finding="Passing through doorways increased forgetting",
                                url="https://doi.org/10.1080/17470218.2011.571267", replication="mixed")],
        loop_line="So next time you walk through a door", caption="Why you forget when you walk into a room",
        hashtags=["#psychology", "#brain"], comment_prompt="What did you forget today?",
        thumbnail_text="Doorway effect", search_keywords=["why do i forget"])


def messy_script() -> content.Script:
    s = clean_script()
    s.beats[2].scene_id = 99                                   # no such scene
    s.beats[3].onscreen.append(content.TextPart(text="twice", kind="key"))  # two key parts
    s.beats[4].source_index = 7                                # out of range
    return s


def seed_channel(w: FakeWorld) -> dict:
    from studio import seed
    ch = copy.deepcopy(seed.CHANNELS[0])
    ch.update(id=str(uuid.uuid4()), require_approval=True, min_seconds=65, max_seconds=95, status="active")
    w.tables["channels"].append(ch)
    for name in ("anthropic", "voice", "runpod", "tiktok", "storage", "worker"):
        w.tables["services"].append({"name": name, "status": "ok"})
    return ch


def seed_video(w: FakeWorld, ch: dict) -> dict:
    return w.insert("videos", {"channel_id": ch["id"], "title": "Doorway effect", "status": "queued",
                               "idea_id": None, "cost_breakdown": {}, "cost_usd": 0})[0]


def install(monkeypatch, work_dir: Path) -> FakeWorld:
    w = FakeWorld()
    for name in ("select", "insert", "update", "delete", "rpc", "upload", "download", "remove", "list_objects"):
        monkeypatch.setattr(db, name, getattr(w, name))
    monkeypatch.setattr(llm, "structured", w.structured)
    monkeypatch.setattr(llm, "research", w.research)
    monkeypatch.setattr(images, "generate", w.generate)
    monkeypatch.setattr(voice, "synthesize", w.synthesize)
    monkeypatch.setattr(config, "WORK", work_dir)
    settings._cache.clear()
    return w


def probe(data: bytes) -> dict:
    import json
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(data)
        f.flush()
        out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f.name],
                             capture_output=True, text=True, check=True).stdout
    return json.loads(out)


__all__ = ["FakeWorld", "install", "seed_channel", "seed_video", "clean_script", "messy_script", "probe", "BytesIO",
           "pipeline"]
