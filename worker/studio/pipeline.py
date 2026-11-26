"""produce_video: the full production line for one video, resumable stage by stage."""
from __future__ import annotations

import dataclasses
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import zlib
from typing import Callable
from concurrent.futures import ThreadPoolExecutor
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
    if "problems" in fc:                                   # the light content check (phase 2)
        return bool(fc.get("passed")) and not fc["problems"]
    if "blocking" in fc:                                   # older fact-check results
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


def _check_and_fix(video: dict, ch: dict, idea: dict, script: content.Script
                   ) -> tuple[content.Script, content.PolicyCheck]:
    """Light check; one targeted fix round and one re-check. Still a problem → PermanentError with the reason."""
    fc, usd = content.policy_check(ch, script, video_id=video["id"])
    _add_cost(video, "factcheck", usd)
    long = content.length_problem(script, ch)
    if fc.ok() and not long:
        return script, fc
    fixes = [f"Line [{p.line}]: {p.issue} → {p.fix}" if p.line is not None else f"{p.issue} → {p.fix}"
             for p in fc.problems] + ([long] if long else [])
    _upd(video["id"], stage_detail="Fixing what the check flagged")
    script, usd = content.write_script(ch, idea, video["research"],
                                       hook_style=(video.get("experiment") or {}).get("hook_style", "you-callout"),
                                       feedback=["Change only what this asks, keep everything else: " + f for f in fixes],
                                       previous=script.model_dump(), video_id=video["id"])
    _add_cost(video, "script", usd)
    script = content.keep_found_sources(script, (video.get("research") or {}).get("citations") or [])
    fc, usd = content.policy_check(ch, script, video_id=video["id"])
    _add_cost(video, "factcheck", usd)
    long = content.length_problem(script, ch)
    if not fc.ok() or long:
        why = "; ".join([p.issue for p in fc.problems] + ([long] if long else []))
        _upd(video["id"], factcheck=fc.model_dump())
        raise PermanentError("Content check failed after one fix: " + why[:400])
    return script, fc


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


def produce(video_id: str, from_stage: str | None = None, *, stop_after: str | None = None,
            on_cleared: Callable[[], None] | None = None) -> dict:
    """Run the line for one video. `stop_after` (test runs) ends after that stage without counting as a failure.
    `on_cleared` is called once the redo of `from_stage` has wiped its outputs, so retries don't wipe again."""
    if stop_after is not None and stop_after not in STAGES:
        raise PermanentError(f"Unknown stop_after stage '{stop_after}' (use one of {', '.join(STAGES)})")
    video = db.select("videos", {"id": video_id}, single=True)
    if not video:
        raise RuntimeError(f"video {video_id} not found")
    ch = db.select("channels", {"id": video["channel_id"]}, single=True)
    idea = db.select("ideas", {"id": video["idea_id"]}, single=True) if video.get("idea_id") else \
        {"title": video["title"], "angle": "", "hook": "", "sources": []}
    work = config.WORK / "videos" / video_id
    work.mkdir(parents=True, exist_ok=True)

    start = STAGES.index(from_stage) if from_stage in STAGES else 0
    redo_visuals = bool(from_stage) and STAGES.index(from_stage) <= STAGES.index("visuals")
    if from_stage:
        # wipe outputs of the stage being redone and everything after it
        clear = {"research": dict(research=None, script=None, scorecard=None, factcheck=None),
                 "script": dict(script=None, scorecard=None, factcheck=None),
                 "factcheck": dict(factcheck=None)}.get(from_stage, {})
        if STAGES.index(from_stage) <= STAGES.index("render"):
            clear.update(video_path=None, thumb_path=None, duration_s=None)
            library_path(video_id).unlink(missing_ok=True)
        base = f"{ch['slug']}/{video_id}"
        if STAGES.index(from_stage) <= STAGES.index("visuals"):
            shutil.rmtree(work / "scenes", ignore_errors=True)
            _remove_stored(f"{base}/scenes/", [f"{base}/scenes/{i}.png" for i in range(12)])
        if STAGES.index(from_stage) <= STAGES.index("voice"):
            (work / "voice.mp3").unlink(missing_ok=True)
            (work / "words.json").unlink(missing_ok=True)
            _remove_stored(None, [f"{base}/voice.mp3", f"{base}/words.json"])
            clear["audio_path"] = None
        video.update(_upd(video_id, approval=None, **clear))
        if on_cleared:
            on_cleared()

    secs: dict[str, float] = {}
    for name in STAGES[start:]:
        t0 = time.monotonic()
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
            _stage(video, name, "Checking tone, TikTok rules and length")
            script = content.Script.model_validate(video["script"])
            script, fc = _check_and_fix(video, ch, idea, script)
            video.update(_upd(video_id, factcheck=fc.model_dump(), script=script.model_dump(), title=script.title,
                              caption=script.caption, hashtags=script.hashtags))

        elif name == "visuals":
            script = content.Script.model_validate(video["script"])
            sdir = work / "scenes"
            sdir.mkdir(exist_ok=True)
            for s in script.scenes:            # resumed on a fresh machine: reuse drawings already paid for
                if not redo_visuals and not (sdir / f"{s.id}.png").exists():
                    _restore(f"{ch['slug']}/{video_id}/scenes/{s.id}.png", sdir / f"{s.id}.png")
            need = [s for s in script.scenes if not (sdir / f"{s.id}.png").exists()]
            if need:
                _stage(video, name, f"Drawing {len(need)} scenes")
                _draw_scenes(video, ch, need, sdir)

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
            if video.get("cover_ms") is not None:       # keep the cover the owner picked across a re-render
                try:
                    cover_frame(Path(out["path"]), int(video["cover_ms"]), Path(out["thumb"]))
                except RuntimeError as e:
                    log.warning(f"cover frame: {e}")
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

        secs[name] = round(time.monotonic() - t0, 1)
        if stop_after == name:
            return _stop_test(video, ch, name, secs)

    approved = not ch.get("require_approval", True)
    video.update(_upd(video_id, status="approved" if approved else "ready", progress=100, stage_detail=None,
                      approval=None if approved else "pending", error=None))
    event(f"Ready: {video['title']} ({video.get('duration_s')}s, ${video.get('cost_usd', 0):.2f})"
          + ("" if approved else " — waiting for your approval"), "success", "pipeline",
          channel_id=ch["id"], video_id=video_id, data={"seconds": secs})
    shutil.rmtree(work, ignore_errors=True)
    return video


def _stop_test(video: dict, ch: dict, stage: str, secs: dict) -> dict:
    """A test run ends here: parked as 'rejected' so it never posts, never blocks the channel, never trips the
    failure breaker."""
    video.update(_upd(video["id"], status="rejected", approval="rejected", progress=PROGRESS[stage],
                      rejection_note=f"Test run: stopped after {stage}", stage_detail=f"Test stopped after {stage}",
                      error=None))
    from .ops import release_idea              # lazy: ops imports pipeline
    release_idea(video["id"], failed=False)
    event(f"Test run stopped after {stage}: " + ", ".join(f"{k} {v:.0f}s" for k, v in secs.items()), "info",
          "pipeline", channel_id=ch["id"], video_id=video["id"], data={"seconds": secs})
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


def cover_frame(src: Path, ms: int, dst: Path) -> None:
    """One frame at `ms` as a 1080-wide JPEG: the cover the owner picked."""
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, ms) / 1000:.3f}", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=1080:-2", "-q:v", "3", str(dst)],
                       capture_output=True, text=True)
    if p.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError("Could not grab the cover frame: " + (p.stderr or "no frame at that time")[-300:])


def make_thumb(video_id: str) -> dict:
    """Rebuild thumb.jpg from the frame the owner picked (videos.cover_ms). Reads the full-quality disk copy, or the
    dashboard preview when the disk copy is gone."""
    v = db.select("videos", {"id": video_id}, single=True)
    if not v:
        raise PermanentError("That video doesn't exist any more")
    if v.get("cover_ms") is None:
        return {"skipped": "no cover picked"}
    ch = db.select("channels", {"id": v["channel_id"]}, single=True)
    ms = int(v["cover_ms"])
    if v.get("duration_s"):
        ms = min(ms, max(0, int(float(v["duration_s"]) * 1000) - 200))
    work = config.WORK / "thumbs" / video_id
    work.mkdir(parents=True, exist_ok=True)
    try:
        src = library_path(video_id)
        if not src.exists():
            if not v.get("video_path"):
                raise PermanentError("This video has no file yet, so there is no frame to pick")
            src = work / "src.mp4"
            src.write_bytes(db.download("videos", v["video_path"]))
        out = work / "thumb.jpg"
        cover_frame(src, ms, out)
        path = f"{ch['slug']}/{video_id}/thumb.jpg"
        db.upload("videos", path, out.read_bytes(), "image/jpeg")
        _upd(video_id, thumb_path=path)
        event(f"Cover updated: {v.get('title') or 'video'} (frame at {ms / 1000:.1f}s)", "success", "dashboard",
              channel_id=ch["id"], video_id=video_id)
        return {"thumb": path, "ms": ms}
    finally:
        shutil.rmtree(work, ignore_errors=True)


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


SCENE_WORKERS = 4


def _scene_prompt(description: str) -> str:
    return description.rstrip(". ") + ", props drawn as simple white outlines, no symbols, no text"


def _draw_scenes(video: dict, ch: dict, scenes: list, sdir: Path) -> None:
    """Draw scenes on RunPod in parallel (≤4). Each finished scene is saved and uploaded at once, so a failure
    of one never costs the others; the first error is raised after all have finished."""
    style = ch.get("style") or {}
    lock = threading.Lock()
    done = {"n": 0}

    def one(s) -> None:
        img, usd = images.generate(_scene_prompt(s.description), seed=int(style.get("seed", 7)) + s.id,
                                   figure_prompt=style.get("figure_prompt"), channel_id=ch["id"], video_id=video["id"])
        img.save(sdir / f"{s.id}.png")
        db.upload("videos", f"{ch['slug']}/{video['id']}/scenes/{s.id}.png", (sdir / f"{s.id}.png").read_bytes(),
                  "image/png")
        with lock:
            _add_cost(video, "images", usd)
            done["n"] += 1
            _upd(video["id"], stage_detail=f"Drawing scenes ({done['n']} of {len(scenes)} done)")

    errors = []
    with ThreadPoolExecutor(max_workers=min(SCENE_WORKERS, len(scenes))) as pool:
        for f in [pool.submit(one, s) for s in scenes]:
            try:
                f.result()
            except BaseException as e:      # keep waiting for the rest so their work is saved
                errors.append(e)
    if errors:      # a budget stop or a service outage parks the job; prefer it over a plain retryable error
        raise next((e for e in errors if isinstance(e, (spend.BudgetReached, ServiceProblem))), errors[0])


def _remove_stored(prefix: str | None, fallback: list[str]) -> None:
    """Delete a redone stage's files from storage so a resume never restores the old ones."""
    paths = list(fallback)
    if prefix:
        try:
            paths += [prefix + o["name"] for o in db.list_objects("videos", prefix) if o.get("name")]
        except Exception as e:
            log.info(f"list {prefix}: {e}")
    try:
        db.remove("videos", sorted(set(paths)))
    except Exception as e:
        log.warning(f"could not remove old files: {e}")


def _restore(storage_path: str, dest: Path) -> bool:
    """Copy a file this video already produced back from storage. False when it isn't there."""
    try:
        data = db.download("videos", storage_path)
    except db.DBError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


SPEED_MIN, SPEED_MAX = 0.92, 1.10


def _learn_wps(ch: dict, words: int, seconds: float, speed: float) -> None:
    """Running average (last ~5 voices) of this channel's real pace at speed 1.0, so scripts get the right length."""
    if words < 30 or seconds <= 0:
        return
    cur = db.select("channels", {"id": ch["id"]}, single=True, columns="voice") or {}
    v = dict(cur.get("voice") or ch.get("voice") or {})
    x = words / seconds / max(0.5, speed)
    n = int(v.get("wps_n") or 0)
    avg = float(v.get("wps") or x)
    avg = x if n == 0 else avg + (x - avg) / min(n + 1, 5)
    v.update(wps=round(avg, 4), wps_n=min(n + 1, 5) if n < 5 else 5)
    db.update("channels", {"id": ch["id"]}, {"voice": v})
    ch["voice"] = v


def _voice_with_length_gate(video: dict, ch: dict, idea: dict, work: Path) -> None:
    """Fit the voice into the channel's window: measured pace → speed nudge (free) → one narration rewrite (rare)."""
    script = content.Script.model_validate(video["script"])
    min_s = max(HARD_MIN_SECONDS, float(ch.get("min_seconds") or 65))
    max_s = float(ch.get("max_seconds") or 95) + 8
    target = (min_s + max_s - 8) / 2
    base = dict(ch.get("voice") or {})
    base_speed = float(base.get("speed") or 1.0)

    def synth(sc: content.Script, speed: float):
        cfg = {**base, "speed": round(speed, 3)}
        audio, words, usd = voice.synthesize(content.spoken_text(sc), cfg, channel_id=ch["id"], video_id=video["id"])
        _add_cost(video, "voice", usd)
        dur = (words[-1].end if words else 0) + 0.7
        _learn_wps(ch, len(words), dur, speed)
        return audio, words, dur

    audio, words, dur = synth(script, base_speed)
    if not min_s <= dur <= max_s:                       # 1) speed nudge, no rewrite
        speed = base_speed * min(SPEED_MAX, max(SPEED_MIN, dur / target))
        _upd(video["id"], stage_detail=f"Voice was {dur:.0f}s — adjusting the speaking speed")
        audio, words, dur = synth(script, speed)
    if not min_s <= dur <= max_s:                       # 2) one narration rewrite, scenes kept
        wc = content.word_count(script)
        goal = int(wc * target / dur)
        verb = "LENGTHEN" if dur < min_s else "SHORTEN"
        event(f"Voice length {dur:.1f}s outside {min_s:.0f}-{max_s:.0f}s even after a speed change; rewriting to ~{goal} words",
              "warn", "pipeline", channel_id=ch["id"], video_id=video["id"])
        _upd(video["id"], stage_detail=f"Voice was {dur:.0f}s — adjusting the script length")
        script, usd = content.write_script(
            ch, idea, video["research"], hook_style=(video.get("experiment") or {}).get("hook_style", "you-callout"),
            feedback=[f"{verb} the narration to about {goal} words total (currently {wc}). Keep every fact, the hook and "
                      f"loop line. Add depth from the research, never filler. Keep the scenes list EXACTLY as it is "
                      f"and only use existing scene ids."],
            previous=script.model_dump(), video_id=video["id"])
        _add_cost(video, "script", usd)
        old_scenes = content.Script.model_validate(video["script"]).scenes
        ids = {sc.id for sc in old_scenes}
        script.scenes = old_scenes
        for b in script.beats:
            if b.scene_id not in ids:
                b.scene_id = old_scenes[0].id
        script = content.keep_found_sources(script, (video.get("research") or {}).get("citations") or [])
        # any rewrite must pass the content check again before it can be voiced
        _upd(video["id"], stage_detail="Re-checking the script after the length edit")
        fc, usd = content.policy_check(ch, script, video_id=video["id"])
        _add_cost(video, "factcheck", usd)
        if not fc.ok():
            raise PermanentError("Content check failed after the length edit: "
                                 + "; ".join(p.issue for p in fc.problems)[:400])
        video.update(_upd(video["id"], script=script.model_dump(), factcheck=fc.model_dump()))
        audio, words, dur = synth(script, base_speed)
    if dur < HARD_MIN_SECONDS:
        raise RuntimeError(f"Voiceover is only {dur:.1f}s; Creator Rewards needs > 60s")
    (work / "voice.mp3").write_bytes(audio)
    (work / "words.json").write_text(json.dumps([[w.text, w.start, w.end] for w in words]))
    base_path = f"{ch['slug']}/{video['id']}"
    db.upload("videos", f"{base_path}/voice.mp3", audio, "audio/mpeg")
    db.upload("videos", f"{base_path}/words.json", (work / "words.json").read_bytes(), "application/json")
    _upd(video["id"], audio_path=f"{base_path}/voice.mp3")


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


RENDER_TIMEOUT_S = 1500


def _check_probe(pr: dict) -> None:
    if pr["duration"] < HARD_MIN_SECONDS:
        raise RuntimeError(f"Rendered video is {pr['duration']:.1f}s (< 61s)")
    if not pr.get("acodec"):
        raise RuntimeError("Rendered video has no audio track")


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
        stdout, stderr = proc.communicate(timeout=RENDER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)          # kill the pool workers and ffmpeg children too
        proc.communicate()
        raise RuntimeError(f"Render took longer than {RENDER_TIMEOUT_S // 60} minutes and was stopped")
    if proc.returncode != 0:
        raise RuntimeError("Render failed: " + (stderr or stdout)[-800:])
    pr = json.loads(stdout.strip().splitlines()[-1])
    _check_probe(pr)
    return {"path": out, "thumb": thumb, "probe": pr}
