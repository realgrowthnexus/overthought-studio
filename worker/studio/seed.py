"""Seed the 5 launch channels and Overthought's idea bank. Idempotent (upserts by slug / skips existing ideas).

Run:  python -m studio.seed
Channels are created PAUSED. Start them from the dashboard once a TikTok account is connected.
"""
from __future__ import annotations

from . import db

BASE_FIGURE = ("classic stick figure made of single thin white lines: circle head, one straight line body, two line arms, "
               "two line legs, on pure black background, flat minimal hand-drawn vector, monochrome white lines only, "
               "no shading, no text, no letters, no numbers, no logos, no signature, no watermark, ")
COMMON_RULES = [
    "Every claim cites a real, findable study or reputable source, shown as → Researcher · Institution · Year.",
    "Flag effects that failed to replicate (e.g. ego depletion, power posing) instead of presenting them as fact.",
    "Never round a stat into something false.",
    "US references: dollars, US stores, US school and work life.",
]

CHANNELS = [
    {
        "slug": "overthought", "name": "Overthought", "sort": 1, "color": "#FFD60A",
        "niche": "Everyday psychology: why your brain does that",
        "description": "Relatable brain glitches explained with real studies and tiny stick figures. Late-night inner voice.",
        "style": {"preset": "charcoal", "bg": "#111111", "ink": "#F6F1E6", "accent": "#FFD60A",
                  "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf", "figure_prompt": BASE_FIGURE,
                  "seed": 7, "bug_text": "overthought", "music_seed": 11},
        "voice": {"provider": "kokoro", "voice": "am_michael+am_fenrir", "speed": 1.0},
        "content": {"audience": "US, English, ages 16-34",
                    "tone": "Calm, warm, slightly amused — like a smart friend at 2 a.m. Never preachy.",
                    "pillars": [{"name": "Why you do that", "weight": 0.7}, {"name": "Spot the trick", "weight": 0.3}],
                    "hook_styles": ["you-callout", "myth-bust", "number", "question", "pov"],
                    "hashtags_core": ["#psychology", "#brainfacts", "#didyouknow", "#overthinking"],
                    "rules": COMMON_RULES + ["'Spot the trick' is always framed as protecting yourself."],
                    "banned": ["medical diagnosis", "how to manipulate people"]},
    },
    {
        "slug": "money-brain", "name": "Money Brain", "sort": 2, "color": "#3DDC97",
        "niche": "The psychology of money: traps, prices and habits (US personal finance)",
        "description": "Why smart people make dumb money moves — behavioral economics with receipts.",
        "style": {"preset": "ledger", "bg": "#0F1412", "ink": "#EAF2EC", "accent": "#3DDC97",
                  "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf", "figure_prompt": BASE_FIGURE,
                  "seed": 21, "bug_text": "money brain", "music_seed": 23},
        "voice": {"provider": "kokoro", "voice": "am_onyx", "speed": 1.0},
        "content": {"audience": "US, ages 18-34, early career, students, renters",
                    "tone": "Sharp, friendly, a little cheeky; zero finance-bro energy. Education only, never advice.",
                    "pillars": [{"name": "Money traps", "weight": 0.5}, {"name": "Pricing tricks", "weight": 0.3},
                                {"name": "Habits that work", "weight": 0.2}],
                    "hook_styles": ["you-callout", "number", "myth-bust", "question", "dollar-shock"],
                    "hashtags_core": ["#moneytok", "#personalfinance", "#psychology", "#didyouknow"],
                    "rules": COMMON_RULES + ["General education only — never individual financial advice or stock picks."],
                    "banned": ["specific investment advice", "crypto pumping", "get-rich-quick"]},
    },
    {
        "slug": "tiny-history", "name": "Tiny History", "sort": 3, "color": "#FF7A59",
        "niche": "Strange true history stories in about a minute",
        "description": "Weird, true, well-sourced history moments told by tiny stick figures.",
        "style": {"preset": "ember", "bg": "#14110F", "ink": "#F3E9DC", "accent": "#FF7A59",
                  "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf", "figure_prompt": BASE_FIGURE,
                  "seed": 33, "bug_text": "tiny history", "music_seed": 37},
        "voice": {"provider": "kokoro", "voice": "bm_george", "speed": 1.0},
        "content": {"audience": "US, ages 16-34, curious, loves 'wait, that really happened?'",
                    "tone": "Storyteller by a campfire: suspense, dry humor, then the twist. Respectful of real people.",
                    "pillars": [{"name": "Unbelievable but true", "weight": 0.5}, {"name": "History myths busted", "weight": 0.3},
                                {"name": "US history oddities", "weight": 0.2}],
                    "hook_styles": ["story-cold-open", "myth-bust", "number", "question", "pov"],
                    "hashtags_core": ["#history", "#historytok", "#didyouknow", "#truestory"],
                    "rules": COMMON_RULES + ["Cite historians, primary sources or reputable archives; mark legends as legends."],
                    "banned": ["graphic violence", "glorifying atrocities"]},
    },
    {
        "slug": "how-it-works", "name": "How It Works", "sort": 4, "color": "#4CC9F0",
        "niche": "Everyday science and tech explained simply",
        "description": "Why ice floats, how GPS knows where you are — everyday science in one minute.",
        "style": {"preset": "blueprint", "bg": "#0D1117", "ink": "#E6F1FF", "accent": "#4CC9F0",
                  "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf", "figure_prompt": BASE_FIGURE,
                  "seed": 45, "bug_text": "how it works", "music_seed": 41},
        "voice": {"provider": "kokoro", "voice": "af_heart", "speed": 1.0},
        "content": {"audience": "US, ages 16-34, curious about how everyday things work",
                    "tone": "Clear, playful, wonder-first; one great analogy per video.",
                    "pillars": [{"name": "Everyday objects", "weight": 0.4}, {"name": "Your body", "weight": 0.3},
                                {"name": "Tech you use daily", "weight": 0.3}],
                    "hook_styles": ["question", "you-callout", "number", "myth-bust", "pov"],
                    "hashtags_core": ["#science", "#howitworks", "#learnontiktok", "#didyouknow"],
                    "rules": COMMON_RULES + ["Use peer-reviewed sources, NASA/NIST/NIH or university explainers."],
                    "banned": ["medical advice", "dangerous experiments"]},
    },
    {
        "slug": "myth-busted", "name": "Myth Busted", "sort": 5, "color": "#FF4D6D",
        "niche": "Famous 'facts' that are wrong — corrected with real studies",
        "description": "That thing everyone believes? Here's what the research actually says.",
        "style": {"preset": "stamp", "bg": "#121212", "ink": "#F5F5F5", "accent": "#FF4D6D",
                  "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf", "figure_prompt": BASE_FIGURE,
                  "seed": 57, "bug_text": "myth busted", "music_seed": 53},
        "voice": {"provider": "kokoro", "voice": "af_bella", "speed": 1.0},
        "content": {"audience": "US, ages 16-34",
                    "tone": "Confident, witty, never smug; 'here's the receipt' energy.",
                    "pillars": [{"name": "Body & health myths", "weight": 0.35}, {"name": "Brain myths", "weight": 0.35},
                                {"name": "Everyday myths", "weight": 0.3}],
                    "hook_styles": ["myth-bust", "you-callout", "number", "question", "pov"],
                    "hashtags_core": ["#mythbusting", "#didyouknow", "#science", "#factcheck"],
                    "rules": COMMON_RULES + ["State the myth, the evidence, and what is actually true; note nuance."],
                    "banned": ["medical diagnosis", "anti-vaccine content"]},
    },
]

OVERTHOUGHT_IDEAS = [
    # (title, pillar, study hint)
    ("The doorway effect: why you forget what you came for", "Why you do that", "Radvansky · Notre Dame · 2011"),
    ("Cocktail party effect: hearing your name across a loud room", "Why you do that", "Cherry · 1953; Moray · 1959"),
    ("Hypnic jerk: why you 'fall' as you drift off", "Why you do that", "Sleep research reviews"),
    ("Earworms: why songs get stuck in your head", "Why you do that", "Jakubowski · Goldsmiths · 2017"),
    ("2 a.m. cringe: why old embarrassing moments replay at night", "Why you do that", "Rumination / sleep studies"),
    ("Why you can't tickle yourself", "Why you do that", "Blakemore · UCL · 1998"),
    ("Why time speeds up as you get older", "Why you do that", "Wittmann; proportional theory"),
    ("The spotlight effect: nobody noticed as much as you think", "Why you do that", "Gilovich · Cornell · 2000"),
    ("Frequency illusion: why you suddenly see it everywhere", "Why you do that", "Zwicky · Stanford · 2005"),
    ("Pareidolia: why you see faces in outlets and clouds", "Why you do that", "Liu et al. · Cortex · 2014"),
    ("Phantom vibrations: feeling your phone buzz when it didn't", "Why you do that", "Rothberg · 2010; Drouin · 2012"),
    ("Why you procrastinate on the important task, not the small ones", "Why you do that", "Sirois & Pychyl; mood repair"),
    ("Shower arguments: why you win fights in your head later", "Why you do that", "Counterfactual thinking research"),
    ("Why you forget your dreams minutes after waking", "Why you do that", "Vallat · 2017"),
    ("Why strangers tell you their secrets", "Why you do that", "Stranger-on-a-train phenomenon research"),
    ("The chameleon effect: why you copy people's gestures", "Why you do that", "Chartrand & Bargh · NYU · 1999"),
    ("Peak-end rule: why the ending rewrites the whole memory", "Why you do that", "Kahneman et al. · 1993"),
    ("Why waiting with nothing to do feels twice as long", "Why you do that", "Maister · 1985; Houston airport"),
    ("Loss aversion: why losing $20 hurts more than finding $20", "Why you do that", "Kahneman & Tversky · 1979"),
    ("Sunk cost: why you finish the bad movie", "Why you do that", "Arkes & Blumer · Ohio · 1985"),
    ("The decoy effect: why the medium popcorn exists", "Spot the trick", "Huber, Payne & Puto · Duke · 1982"),
    ("Why everything costs $9.99", "Spot the trick", "Thomas & Morwitz · 2005"),
    ("Ben Franklin effect: ask a favor to be liked", "Spot the trick", "Jecker & Landy · 1969"),
    ("The confidence heuristic: why we trust loud people", "Spot the trick", "Price & Stone · 2004"),
    ("Foot in the door: the small yes that leads to a big yes", "Spot the trick", "Freedman & Fraser · Stanford · 1966"),
    ("Why silence makes people keep talking", "Spot the trick", "Conversation research / interview tactics"),
    ("The power of 'FREE': why $0 breaks your math", "Spot the trick", "Shampanier, Mazar & Ariely · MIT · 2007"),
    ("'Only 2 left!': scarcity and your brain", "Spot the trick", "Worchel · 1975 cookie jar study"),
    ("Red notification dots: why you can't ignore them", "Spot the trick", "Variable reward / attention research"),
    ("The bystander effect — and the Kitty Genovese myth", "Spot the trick", "Darley & Latané · 1968; Manning et al. · 2007"),
    ("Invisible gorilla: half of people miss it", "Why you do that", "Simons & Chabris · Harvard · 1999"),
    ("Your memories aren't recordings: one word changes them", "Why you do that", "Loftus & Palmer · 1974"),
    ("Ego depletion: the famous willpower study that didn't replicate", "Why you do that", "Baumeister 1998; Hagger 2016"),
    ("Power posing: what the research really says now", "Spot the trick", "Carney 2010; Ranehill 2015"),
    ("Why you say 'you too' when the waiter says enjoy your meal", "Why you do that", "Speech error / scripts research"),
    ("The Zeigarnik effect: why unfinished things haunt you", "Why you do that", "Zeigarnik · 1927; Masicampo 2011"),
    ("Why you rehearse conversations that never happen", "Why you do that", "Prospective simulation research"),
]


def run() -> None:
    for c in CHANNELS:
        row = dict(c)
        existing = db.select("channels", {"slug": c["slug"]}, single=True)
        if existing:
            db.update("channels", {"slug": c["slug"]}, {k: v for k, v in row.items() if k not in ("slug",)})
        else:
            row.update(status="paused", posting_mode="draft", require_approval=True, posts_per_day=1,
                       post_times=["12:30", "19:30"], min_seconds=65, max_seconds=90)
            db.insert("channels", row)
    ot = db.select("channels", {"slug": "overthought"}, single=True)
    have = {r["title"] for r in db.select("ideas", {"channel_id": ot["id"]}, columns="title")}
    rows = []
    for i, (t, pillar, study) in enumerate(OVERTHOUGHT_IDEAS):
        if t in have:
            continue
        rows.append({"channel_id": ot["id"], "title": t, "pillar": pillar, "sources": [{"study": study}],
                     "score": round(8.6 - i * 0.05, 2), "origin": "seed",
                     "angle": "Protect yourself" if pillar == "Spot the trick" else "Why you do that"})
    if rows:
        db.insert("ideas", rows)
    print(f"channels: {len(CHANNELS)}, new overthought ideas: {len(rows)}")


if __name__ == "__main__":
    run()
