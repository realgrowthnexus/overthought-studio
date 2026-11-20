"""Assembles the guide with ffmpeg: a title card per chapter, then each scene clip with its narration and
burned-in Roman Urdu subtitles. Writes the master MP4, the full SRT and the chapter list.

  python tools/guide/compose.py [--chapter N]      → <GUIDE_OUT>/overthought-guide-ur-master.mp4 (or chapter-N.mp4)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_script  # noqa: E402
import srt  # noqa: E402
from tts import OUT, Cue  # noqa: E402

TITLE_S = 3.0
FPS = 30
KALAM = ROOT / "assets" / "style" / "fonts" / "Kalam-Bold.ttf"
SUB_FONT = "Inter"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]


def build_timeline(script: dict, narration: dict, title_s: float = TITLE_S):
    """Segments in play order with absolute start times, all subtitle cues on the global clock, chapter starts."""
    segs, cues, chapters, t = [], [], [], 0.0
    for ch in script["chapters"]:
        chapters.append((round(t, 3), ch["title_roman"]))
        segs.append({"kind": "title", "chapter": ch["id"], "title": ch["title_roman"], "start": round(t, 3),
                     "duration": title_s})
        t += title_s
        for sc in ch["scenes"]:
            n = narration[sc["id"]]
            segs.append({"kind": "scene", "id": sc["id"], "start": round(t, 3), "duration": n["duration"]})
            cues += [Cue(round(t + s, 3), round(t + e, 3), r) for s, e, r in n["cues"]]
            t += n["duration"]
    return segs, cues, chapters


def chapter_lines(chapters: list[tuple[float, str]]) -> str:
    return "".join(f"{int(s // 60):02d}:{int(s % 60):02d} {i}. {title}\n" for i, (s, title) in enumerate(chapters, 1))


def _ass(cues: list, path: Path) -> None:
    def ts(t: float) -> str:
        cs = int(round(t * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Sub,{SUB_FONT},54,&H00FFFFFF,&H00FFFFFF,&H10111111,&H10111111,1,0,0,0,100,100,0,0,3,18,0,2,"
            "260,260,56,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = [f"Dialogue: 0,{ts(c.start)},{ts(c.end + 0.25)},Sub,,0,0,0,,{c.roman}" for c in cues]
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def render_title(seg: dict, out: Path) -> None:
    font = str(KALAM).replace(":", "\\:")
    vf = (f"drawtext=fontfile='{font}':text='Hissa {seg['chapter']}':fontcolor=0xFFD60A:fontsize=56:"
          f"x=(w-text_w)/2:y=h/2-150,"
          f"drawtext=fontfile='{font}':text='{_esc(seg['title'])}':fontcolor=0xF6F1E6:fontsize=120:"
          f"x=(w-text_w)/2:y=h/2-40,"
          f"drawbox=x=(iw-360)/2:y=ih/2+130:w=360:h=6:color=0xFFD60A:t=fill,"
          f"fade=t=in:st=0:d=0.4,fade=t=out:st={seg['duration'] - 0.4}:d=0.4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=0x111111:s=1920x1080:r={FPS}:d={seg['duration']}", "-f", "lavfi", "-i",
                    f"anullsrc=r=48000:cl=stereo", "-t", str(seg["duration"]), "-vf", vf, *ENC, str(out)], check=True)


def render_scene(seg: dict, narration: dict, out: Path) -> None:
    n = narration[seg["id"]]
    ass = out.with_suffix(".ass")
    _ass([Cue(s, e, r) for s, e, r in n["cues"]], ass)
    clip = OUT / "clips" / f"{seg['id']}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(clip), "-i", n["audio"],
                    "-t", f"{n['duration']:.3f}", "-vf", f"ass='{ass}'", "-map", "0:v", "-map", "1:a", *ENC, str(out)],
                   check=True)


def main(only_chapter: int | None = None) -> Path:
    script = check_script.load(HERE / "script.yaml")
    if only_chapter:
        script = {"chapters": [c for c in script["chapters"] if c["id"] == only_chapter]}
    narration = json.loads((OUT / "narration.json").read_text())
    segs, cues, chapters = build_timeline(script, narration)
    parts = OUT / "parts"
    parts.mkdir(exist_ok=True)
    files = []
    for i, seg in enumerate(segs):
        f = parts / (f"{i:02d}-title-{seg['chapter']}.mp4" if seg["kind"] == "title" else f"{i:02d}-scene-{seg['id']}.mp4")
        (render_title if seg["kind"] == "title" else lambda s, o: render_scene(s, narration, o))(seg, f)
        files.append(f)
        print(f"rendered {f.name}", flush=True)
    lst = parts / "list.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    name = f"chapter-{only_chapter}.mp4" if only_chapter else "overthought-guide-ur-master.mp4"
    out = OUT / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    if not only_chapter:
        (OUT / "overthought-guide-ur.srt").write_text(srt.to_srt(cues), encoding="utf-8")
        (OUT / "chapters.txt").write_text(chapter_lines(chapters), encoding="utf-8")
    return out


if __name__ == "__main__":
    ch = int(sys.argv[sys.argv.index("--chapter") + 1]) if "--chapter" in sys.argv else None
    print(main(ch))
