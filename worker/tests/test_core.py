import json
import os
import subprocess
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw

from studio import config, content, crypto
from studio.images import to_palette
from studio.render import compose, drawon, music
from studio.voice import words_from_alignment


def test_crypto_roundtrip_and_format():
    tok = crypto.encrypt("sk-test-123")
    assert tok.startswith("v1:")
    assert crypto.decrypt(tok) == "sk-test-123"


def test_words_from_alignment():
    text = "Hi there, you."
    starts = [i * 0.1 for i in range(len(text))]
    ends = [s + 0.08 for s in starts]
    ws = words_from_alignment(list(text), starts, ends)
    assert [w.text for w in ws] == ["Hi", "there,", "you."]
    assert ws[1].start == starts[3]


def _script(n_beats=4):
    beats = [content.Beat(kind="hook" if i == 0 else "story", narration=f"word{i} " * 5,
                          onscreen=[content.TextPart(text="hello", kind="ink"), content.TextPart(text="key", kind="key")],
                          scene_id=i % 2, accent="question_mark") for i in range(n_beats)]
    return content.Script(title="t", hook_line="h", hook_style="you-callout", beats=beats,
                          scenes=[content.Scene(id=0, description="a"), content.Scene(id=1, description="b")],
                          sources=[], loop_line="l", caption="c", hashtags=["#a"], comment_prompt="q",
                          thumbnail_text="x", search_keywords=["k"])


def test_beat_times_monotonic():
    from studio.pipeline import _beat_times
    s = _script()
    words = [[f"w{i}", i * 0.4, i * 0.4 + 0.3] for i in range(20)]
    times = _beat_times(s, words)
    assert times[0][0] == 0.0
    assert all(a[1] <= b[0] + 1e-6 or abs(a[1] - b[0]) < 0.2 for a, b in zip(times, times[1:]))
    assert times[-1][1] > words[-1][2]


def test_slots_respect_posts_per_day():
    from studio.scheduler import slots
    ch = {"timezone": "America/New_York", "post_times": ["19:30", "12:30"], "posts_per_day": 1}
    s = slots(ch, 2)
    assert 2 <= len(s) <= 3
    assert all(x.tzinfo is not None for x in s)


def test_palette_maps_black_to_bg():
    im = Image.new("RGB", (32, 32), (0, 0, 0))
    ImageDraw.Draw(im).line([(0, 16), (31, 16)], fill=(255, 255, 255), width=3)
    out = np.asarray(to_palette(im, "#111111", "#F6F1E6"))
    assert tuple(out[0, 0]) == (17, 17, 17)
    assert tuple(out[16, 10]) == (246, 241, 230)


def test_drawon_order_head_first():
    m = np.zeros((200, 200), np.float32)
    m[20:30, 95:105] = 1          # "head"
    m[30:180, 99:101] = 1         # "body" connected below
    o = drawon.order_map(m, work=100)
    assert o[25, 100] < o[170, 100]
    assert drawon.reveal(o, 0).max() == 0 and drawon.reveal(o, 1).min() == 1


def test_music_bed_length():
    b = music.bed(3.0, seed=4)
    assert abs(len(b) - 3 * music.SR) < 10 and np.abs(b).max() <= 1.0


def test_render_short_video(tmp_path):
    # two synthetic scenes, a silent voice track, 2.5 s render
    scenes = {}
    for i in range(2):
        im = Image.new("RGB", (1024, 1024), (0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((480, 300, 560, 380), outline=(255, 255, 255), width=6)
        d.line([(520, 380), (520 + i * 40, 650)], fill=(255, 255, 255), width=6)
        p = tmp_path / f"{i}.png"
        im.save(p)
        scenes[i] = str(p)
    voice = tmp_path / "v.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2.5",
                    str(voice)], check=True)
    beats = [compose.BeatT(0, 1.2, [("why you ", "ink"), ("forget", "key")], 0, "question_mark", None, False, None, "hook"),
             compose.BeatT(1.2, 2.5, [("it's ", "ink"), ("normal", "key")], 1, "number", "25%", True,
                           "→ Radvansky · Notre Dame · 2011", "payoff")]
    words = [("why", 0.0, 0.3), ("you", 0.35, 0.5), ("forget", 0.55, 1.0), ("it's", 1.3, 1.5), ("normal.", 1.6, 2.1)]
    out = tmp_path / "o.mp4"
    spec = compose.Spec(beats=beats, scenes=scenes, words=words, duration=2.5, voice_path=str(voice), style={},
                        out_path=str(out), thumb_path=str(tmp_path / "t.jpg"))
    info = compose.render_video(spec, procs=2)
    assert info["width"] == 1080 and info["height"] == 1920 and info["fps"] == "30/1"
    assert info["vcodec"] == "h264" and info["acodec"] == "aac" and info["pix_fmt"] == "yuv420p"
    assert 2.3 < info["duration"] < 2.7
    assert os.path.exists(tmp_path / "t.jpg")
