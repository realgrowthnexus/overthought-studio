"""produce_video: the full production line for one video, resumable stage by stage."""
from __future__ import annotations

import dataclasses
import json
import os
import signal
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

from . import config, content, db, images, spend, voice
from .log import event, log
from .render import compose
from .services import PermanentError, ServiceProblem

STAGES = ["research", "script", "factcheck", "visuals", "voice", "render"]
STATUS_OF = {"research": "researching", "script": "scripting", "factcheck": "fact_checking", "visuals": "visuals",
             "voice": "voice", "render": "rendering"}
PROGRESS = {"research": 8, "script": 25, "factcheck": 40, "visuals": 55, "voice": 70, "render": 82}
HARD_MIN_SECONDS = 61.0


def _fc_done(fc: dict | None) -> bool:
    if not fc:
        return False
    if "blocking" in fc:
        return not fc["blocking"]
    return bool(fc.get("passes"))


def _upd(vid: str, **vals) -> dict:
    rows = db.update("videos", {"id": vid}, vals)
    return rows[0] if rows else {}


def _add_cost(video: dict, key: str, usd: float) -> None:
    cb = dict(video.get("cost_breakdown") or {})
    cb[key] = round(float(cb.get(key, 0)) + usd, 5)
    video["cost_breakdown"] = cb
    video["cost_usd"] = round(sum(float(v) for v in cb.values()), 5)
    _upd(video["id"], cost_breakdown=cb, cost_usd=video["cost_usd"])


def _stage(video: dict, name: str, detail: str) -> None:
    video.update(_upd(video["id"], status=STATUS_OF[name], stage_detail=detail, progress=PROGRESS[name], error=None))
    event(f"{video.get('title') or 'Video'}: {detail}", "info", "pipeline", channel_id=video["channel_id"],
          video_id=video["id"])


def _blocking_problems(script: content.Script, ch: dict) -> list[str]:
    """After the repair pass: structure must be right; length may be up to 15% outside the target (the voice
    stage fits the rest)."""
    lo, hi = content.word_range(ch)
    wc = content.word_count(script)
    left = [p for p in content.script_problems(script, ch) if "words" not in p]
    if not 0.85 * lo <= wc <= 1.15 * hi:
        left.append(f"The narration is {wc} words; it must be about {lo}-{hi}.")
    return left


def _source_label(s: dict) -> str:
    return f"→ {s['researcher']} · {s['year']}"


def produce(video_id: str, from_stage: str | None = None) -> dict:
    video = db.select("videos", {"id": video_id}, single=True)
    if not video:
        raise RuntimeError(f"video {video_id} not found")
    ch = db.select("channels", {"id": video["channel_id"]}, single=True)
    idea = db.select("ideas", {"id": video["idea_id"]}, single=True) if video.get("idea_id") else \
        {"title": video["title"], "angle": "", "hook": "", "sources": []}
    work = config.WORK / "videos" / video_id
    work.mkdir(parents=True, exist_ok=True)

    start = STAGES.index(from_stage) if from_stage in STAGES else 0
    if from_stage:
        # wipe outputs of the stage being redone and everything after it
        clear = {"research": dict(research=None, script=None, scorecard=None, factcheck=None),
                 "script": dict(script=None, scorecard=None, factcheck=None),
                 "factcheck": dict(factcheck=None)}.get(from_stage, {})
        if STAGES.index(from_stage) <= STAGES.index("render"):
            clear.update(video_path=None, thumb_path=None, duration_s=None)
            library_path(video_id).unlink(missing_ok=True)
        if STAGES.index(from_stage) <= STAGES.index("visuals"):
            shutil.rmtree(work / "scenes", ignore_errors=True)
        if STAGES.index(from_stage) <= STAGES.index("voice"):
            (work / "voice.mp3").unlink(missing_ok=True)
            (work / "words.json").unlink(missing_ok=True)
        video.update(_upd(video_id, approval=None, **clear))

    for name in STAGES[start:]:
        if name == "research" and not video.get("research"):
            _stage(video, name, "Researching the topic and the original study")
            res, usd = content.research_topic(ch, idea, video_id=video_id)
            _add_cost(video, "research", usd)
            video.update(_upd(video_id, research=res))

        elif name == "script" and not video.get("script"):
            _stage(video, name, "Writing the script")
            hook_style = content.pick_hook_style(ch)
            cites = (video.get("research") or {}).get("citations") or []
            script, usd = content.write_script(ch, idea, video["research"], hook_style=hook_style, video_id=video_id)
            _add_cost(video, "script", usd)
            script = content.keep_found_sources(script, cites)
            problems = content.script_problems(script, ch)
            if problems:                       # one repair pass with the exact problems, then accept or retry later
                _upd(video_id, stage_detail="Fixing the script's structure and length")
                script, usd = content.write_script(ch, idea, video["research"], hook_style=hook_style,
                                                   feedback=problems, previous=script.model_dump(), video_id=video_id)
                _add_cost(video, "script", usd)
                script = content.keep_found_sources(script, cites)
                left = _blocking_problems(script, ch)
                if left:
                    raise RuntimeError("Script still has problems after one fix: " + " ".join(left)[:400])
            card = script.self_review
            video.update(_upd(video_id, script=script.model_dump(), scorecard=card.model_dump() if card else None,
                              title=script.title, script_version=(video.get("script_version") or 0) + 1,
                              caption=script.caption, hashtags=script.hashtags,
                              experiment={"hook_style": hook_style}))

        elif name == "factcheck" and not _fc_done(video.get("factcheck")):
            _stage(video, name, "Fact-checking every claim and source")
            script = content.Script.model_validate(video["script"])
            fc = None
            for rnd in range(3):
                fc, usd = content.fact_check(ch, script, video_id=video_id)
                _add_cost(video, "factcheck", usd)
                if fc.ok() or rnd == 2:
                    break
                _upd(video_id, stage_detail="Fixing claims flagged by the fact-check")
                fixes = fc.blocking + fc.minor + [f"{c.claim} → {c.fix}" for c in fc.claims if c.fix]
                if rnd == 1:      # last try: drop what could not be confirmed instead of re-wording it again
                    fixes.append("REMOVE any claim, number or detail above that you cannot support exactly from the "
                                 "research notes; on-screen sources may show just 'Researcher · Year' when the "
                                 "institution is uncertain. A shorter true script beats a detailed doubtful one.")
                script, usd = content.write_script(ch, idea, video["research"],
                                                   hook_style=(video.get("experiment") or {}).get("hook_style", "you-callout"),
                                                   feedback=["ACCURACY FIXES (mandatory): " + f for f in fixes],
                                                   previous=script.model_dump(), video_id=video_id)
                _add_cost(video, "script", usd)
                video.update(_upd(video_id, script=script.model_dump(), title=script.title, caption=script.caption,
                                  hashtags=script.hashtags))
            assert fc is not None
            video.update(_upd(video_id, factcheck=fc.model_dump()))
            if not fc.ok():
                raise PermanentError("Fact-check failed after 2 rewrites: " + "; ".join(fc.blocking)[:500])
            if fc.minor:
                event(f"Fact-check passed with {len(fc.minor)} minor note(s) (not blocking)", "info", "pipeline",
                      channel_id=ch["id"], video_id=video_id)

        elif name == "visuals":
            script = content.Script.model_validate(video["script"])
            sdir = work / "scenes"
            sdir.mkdir(exist_ok=True)
            style = ch.get("style") or {}
            for s in script.scenes:            # resumed on a fresh machine: reuse drawings already paid for
                if not (sdir / f"{s.id}.png").exists():
                    _restore(f"{ch['slug']}/{video_id}/scenes/{s.id}.png", sdir / f"{s.id}.png")
            need = [s for s in script.scenes if not (sdir / f"{s.id}.png").exists()]
            if need:
                _stage(video, name, f"Drawing {len(need)} scenes")
            for i, s in enumerate(need):
                _upd(video_id, stage_detail=f"Drawing scene {i + 1} of {len(need)}")
                img, usd = images.generate(s.description + ", props drawn as simple white outlines, no symbols",
                                           seed=int(style.get("seed", 7)) + s.id, figure_prompt=style.get("figure_prompt"),
                                           channel_id=ch["id"], video_id=video_id)
                img.save(sdir / f"{s.id}.png")
                _add_cost(video, "images", usd)
                db.upload("videos", f"{ch['slug']}/{video_id}/scenes/{s.id}.png", (sdir / f"{s.id}.png").read_bytes(),
                          "image/png")

        elif name == "voice":
            if not (work / "voice.mp3").exists() and video.get("audio_path"):
                base = f"{ch['slug']}/{video_id}"
                if _restore(f"{base}/words.json", work / "words.json"):
                    _restore(f"{base}/voice.mp3", work / "voice.mp3")
            if not (work / "voice.mp3").exists():
                _stage(video, name, "Recording the voiceover")
                _voice_with_length_gate(video, ch, idea, work)

        elif name == "render":
            _stage(video, name, "Animating and editing the video")
            out = _render(video, ch, work)
            _upd(video_id, progress=94, stage_detail="Saving the video and uploading a preview")
            base = f"{ch['slug']}/{video_id}"
            # Full-quality file stays on the VPS disk (free, and publishing reads it without Supabase egress);
            # Supabase only gets a small preview for the dashboard player, so the free plan's 1 GB lasts.
            _keep_final(video_id, Path(out["path"]))
            preview = work / "preview.mp4"
            make_preview(Path(out["path"]), preview)
            db.upload("videos", f"{base}/preview.mp4", preview.read_bytes(), "video/mp4")
            db.upload("videos", f"{base}/thumb.jpg", Path(out["thumb"]).read_bytes(), "image/jpeg")
            script = content.Script.model_validate(video["script"])
            video.update(_upd(video_id, video_path=f"{base}/preview.mp4", thumb_path=f"{base}/thumb.jpg",
                              audio_path=f"{base}/voice.mp3", duration_s=round(out["probe"]["duration"], 2),
                              file_size=out["probe"]["size"], caption=video.get("caption") or script.caption))

    approved = not ch.get("require_approval", True)
    video.update(_upd(video_id, status="approved" if approved else "ready", progress=100, stage_detail=None,
                      approval=None if approved else "pending", error=None))
    event(f"Ready: {video['title']} ({video.get('duration_s')}s, ${video.get('cost_usd', 0):.2f})"
          + ("" if approved else " — waiting for your approval"), "success", "pipeline",
          channel_id=ch["id"], video_id=video_id)
    shutil.rmtree(work, ignore_errors=True)
    return video


def library_path(video_id: str) -> Path:
    """Where the full-quality final.mp4 lives on the VPS (the persistent `work` volume)."""
    return config.WORK / "library" / f"{video_id}.mp4"


def _keep_final(video_id: str, src: Path) -> Path:
    dst = library_path(video_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    shutil.copyfile(src, tmp)
    tmp.replace(dst)                      # atomic: a half-copied file is never picked up for publishing
    return dst


def make_preview(src: Path, dst: Path) -> None:
    """540×960 preview for the dashboard player (~3 MB for 90 s)."""
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=540:-2",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(dst)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("Preview encode failed: " + p.stderr[-400:])


def final_video(video: dict, ch: dict) -> bytes:
    """The full-quality file for TikTok. Normally on disk; if the disk copy is gone (new VPS, cleanup), it is
    rendered again from the saved scenes + voice — free and deterministic — instead of failing the post."""
    lib = library_path(video["id"])
    if lib.exists():
        return lib.read_bytes()
    if (video.get("video_path") or "").endswith("/final.mp4"):        # videos made before the preview change
        return db.download("videos", video["video_path"])
    event(f"{video.get('title') or 'Video'}: full-quality file not on disk, rendering it again", "warn", "publish",
          channel_id=ch["id"], video_id=video["id"])
    work = config.WORK / "videos" / video["id"]
    work.mkdir(parents=True, exist_ok=True)
    try:
        out = _render(video, ch, work)
        return _keep_final(video["id"], Path(out["path"])).read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _restore(storage_path: str, dest: Path) -> bool:
    """Copy a file this video already produced back from storage. False when it isn't there."""
    try:
        data = db.download("videos", storage_path)
    except db.DBError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def _voice_with_length_gate(video: dict, ch: dict, idea: dict, work: Path) -> None:
    script = content.Script.model_validate(video["script"])
    min_s = max(HARD_MIN_SECONDS, float(ch.get("min_seconds") or 65))
    max_s = float(ch.get("max_seconds") or 95) + 8
    for attempt in range(3):
        audio, words, usd = voice.synthesize(content.spoken_text(script), ch.get("voice") or {},
                                             channel_id=ch["id"], video_id=video["id"])
        _add_cost(video, "voice", usd)
        dur = (words[-1].end if words else 0) + 0.7
        if min_s <= dur <= max_s or attempt == 2:
            break
        wc = content.word_count(script)
        target = int(wc * ((min_s + 4) / dur)) if dur < min_s else int(wc * ((max_s - 6) / dur))
        verb = "LENGTHEN" if dur < min_s else "SHORTEN"
        _upd(video["id"], stage_detail=f"Voice was {dur:.0f}s — adjusting script length")
        event(f"Voice length {dur:.1f}s outside {min_s:.0f}-{max_s:.0f}s; rewriting to ~{target} words", "warn",
              "pipeline", channel_id=ch["id"], video_id=video["id"])
        script, usd = content.write_script(
            ch, idea, video["research"], hook_style=(video.get("experiment") or {}).get("hook_style", "you-callout"),
            feedback=[f"{verb} the narration to about {target} words total (currently {wc}). Keep every fact identical, "
                      f"keep the hook and loop line. Add depth (an extra example or detail from the research), never filler. "
                      f"Keep the scenes list EXACTLY as it is and only use existing scene ids."],
            previous=script.model_dump(), video_id=video["id"])
        _add_cost(video, "script", usd)
        # the drawings already exist: keep the original scenes, clamp beats to them
        old_scenes = content.Script.model_validate(video["script"]).scenes
        ids = {sc.id for sc in old_scenes}
        script.scenes = old_scenes
        for b in script.beats:
            if b.scene_id not in ids:
                b.scene_id = old_scenes[0].id
        # any rewrite must pass the fact-check again before it can be voiced
        _upd(video["id"], stage_detail="Re-checking facts after the length edit")
        fc, usd = content.fact_check(ch, script, video_id=video["id"])
        _add_cost(video, "factcheck", usd)
        if not fc.ok():
            raise PermanentError("Length-adjusted script failed the fact-check: " + "; ".join(fc.blocking)[:400])
        video.update(_upd(video["id"], script=script.model_dump(), factcheck=fc.model_dump()))
    if dur < HARD_MIN_SECONDS:
        raise RuntimeError(f"Voiceover is only {dur:.1f}s; Creator Rewards needs > 60s")
    (work / "voice.mp3").write_bytes(audio)
    (work / "words.json").write_text(json.dumps([[w.text, w.start, w.end] for w in words]))
    base = f"{ch['slug']}/{video['id']}"
    db.upload("videos", f"{base}/voice.mp3", audio, "audio/mpeg")
    db.upload("videos", f"{base}/words.json", (work / "words.json").read_bytes(), "application/json")
    _upd(video["id"], audio_path=f"{base}/voice.mp3")


def _beat_times(script: content.Script, words: list[list]) -> list[tuple[float, float]]:
    """Start/end time of each beat from the TTS word timings (word counts per beat, proportional if they differ)."""
    counts = [max(1, len(b.narration.split())) for b in script.beats]
    total, n = sum(counts), len(words)
    starts, acc = [], 0.0
    for c in counts:
        idx = min(n - 1, int(round(acc * n / total)))
        starts.append(words[idx][1])
        acc += c
    end = words[-1][2] + 0.7
    out = []
    for i, s in enumerate(starts):
        st = 0.0 if i == 0 else max(0.0, s - 0.06)
        en = (starts[i + 1] - 0.06) if i + 1 < len(starts) else end
        out.append((st, max(st + 0.3, en)))
    return out


def _render(video: dict, ch: dict, work: Path) -> dict:
    script = content.Script.model_validate(video["script"])
    sdir = work / "scenes"
    if not (sdir / f"{script.scenes[0].id}.png").exists():
        for s in script.scenes:     # resumed on a fresh machine: pull scenes from storage
            sdir.mkdir(exist_ok=True)
            (sdir / f"{s.id}.png").write_bytes(db.download("videos", f"{ch['slug']}/{video['id']}/scenes/{s.id}.png"))
    if not (work / "voice.mp3").exists() or not (work / "words.json").exists():
        base = f"{ch['slug']}/{video['id']}"
        try:
            (work / "voice.mp3").write_bytes(db.download("videos", f"{base}/voice.mp3"))
            (work / "words.json").write_bytes(db.download("videos", f"{base}/words.json"))
        except db.DBError as e:
            raise RuntimeError("Voiceover files are missing; regenerate from the voice stage") from e
    words = json.loads((work / "words.json").read_text())
    times = _beat_times(script, words)
    beats = []
    valid_scenes = {s.id for s in script.scenes}
    for b, (s, e) in zip(script.beats, times):
        src = script.sources[b.source_index] if b.source_index is not None and 0 <= b.source_index < len(script.sources) else None
        keys = [p for p in b.onscreen if p.kind == "key"]
        parts = [(p.text, "key" if (keys and p is keys[0]) else "ink") for p in b.onscreen]
        beats.append(compose.BeatT(start=s, end=e, onscreen=parts,
                                   scene_id=b.scene_id if b.scene_id in valid_scenes else script.scenes[0].id,
                                   accent=b.accent, accent_label=b.accent_label, flash=b.flash,
                                   source=_source_label(src.model_dump()) if src else None, kind=b.kind))
    beats[0].start = 0.0
    style = dict(ch.get("style") or {})
    style.setdefault("bug_text", ch["name"].lower())
    duration = beats[-1].end
    out = str(work / "final.mp4")
    thumb = str(work / "thumb.jpg")
    spec = compose.Spec(beats=beats, scenes={s.id: str(sdir / f"{s.id}.png") for s in script.scenes},
                        words=[(w[0], w[1], w[2]) for w in words], duration=duration,
                        voice_path=str(work / "voice.mp3"), style=style,
                        music_seed=int(style.get("music_seed", zlib.crc32(ch["slug"].encode()) % 97)),
                        out_path=out, thumb_path=thumb)
    spec_path = work / "spec.json"
    spec_path.write_text(json.dumps(dataclasses.asdict(spec)))
    proc = subprocess.Popen([sys.executable, "-m", "studio.render.run", str(spec_path)], cwd=str(config.ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=3600)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)          # kill the pool workers and ffmpeg children too
        proc.communicate()
        raise RuntimeError("Render took longer than 60 minutes and was stopped")
    if proc.returncode != 0:
        raise RuntimeError("Render failed: " + (stderr or stdout)[-800:])
    pr = json.loads(stdout.strip().splitlines()[-1])
    if pr["duration"] < HARD_MIN_SECONDS:
        raise RuntimeError(f"Rendered video is {pr['duration']:.1f}s (< 61s)")
    return {"path": out, "thumb": thumb, "probe": pr}
