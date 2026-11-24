"""Content brain: idea research, script writing, scoring, rewriting, fact-checking."""
from __future__ import annotations

import json
import math
import random
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import llm

# ----------------------------------------------------------------- schemas
AccentKind = Literal["question_mark", "lightbulb", "exclamation", "scribble_cloud", "arrow", "circle",
                     "number", "heart", "clock", "check", "cross", "none"]
BeatKind = Literal["hook", "open_loop", "question", "story", "study", "twist", "fix", "payoff", "loop"]


class TextPart(BaseModel):
    text: str
    kind: Literal["ink", "key"] = Field(description="'key' = the single highlighted keyword of the frame")


class Source(BaseModel):
    researcher: str = Field(description="Lead author surname(s), e.g. 'Radvansky' or 'Gilovich & Savitsky'")
    institution: str = Field(default="", description="Short institution name if known, else empty")
    year: int
    finding: str = Field(description="The specific finding we rely on, with the real numbers")
    url: str = Field(description="Copied EXACTLY from the research SOURCES list")
    replication: Literal["strong", "mixed", "failed", "not_tested"]


class Beat(BaseModel):
    kind: BeatKind
    narration: str = Field(description="Exactly what the voice says in this beat. Natural spoken US English.")
    onscreen: list[TextPart] = Field(description="Short overlay text, max 7 words total, exactly ONE part with kind='key'")
    scene_id: int = Field(description="Which scene image this beat shows (0-based). Reuse ids to keep visual continuity.")
    accent: AccentKind = Field(description="The one yellow glitch element drawn in code on this beat")
    accent_label: Optional[str] = Field(default=None, description="Short label for 'number' accents, e.g. '25%'. Else null.")
    source_index: Optional[int] = Field(default=None, description="Index into sources when this beat cites a study")
    flash: bool = Field(default=False, description="True only on the payoff beat (quick light flash)")


class Scene(BaseModel):
    id: int
    description: str = Field(description="Visual description for a minimalist stick-figure drawing. Concrete action and props. No text, no letters, no logos.")


class Scorecard(BaseModel):
    hook: int = Field(ge=0, le=10)
    curiosity_gap: int = Field(ge=0, le=10)
    viewer_question: int = Field(ge=0, le=10)
    emotional_connection: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)
    pacing: int = Field(ge=0, le=10)
    accuracy_framing: int = Field(ge=0, le=10)
    loop: int = Field(ge=0, le=10)
    originality: int = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)
    biggest_risk: str
    fixes: list[str]


class Script(BaseModel):
    title: str
    hook_line: str = Field(description="Max 9 words. Shown at top of the first frame and spoken first.")
    hook_style: str
    beats: list[Beat]
    scenes: list[Scene]
    sources: list[Source]
    loop_line: str = Field(description="Last spoken line; flows naturally back into the hook_line when the video loops")
    caption: str = Field(description="TikTok caption: searchable first line (what people would type in search) + one curiosity line. No hashtags here.")
    hashtags: list[str] = Field(description="3-5 hashtags mixing niche and broad, each starting with #")
    comment_prompt: str = Field(description="A question to pin as the first comment to drive replies")
    thumbnail_text: str = Field(description="2-4 words for the cover frame")
    search_keywords: list[str] = Field(description="3-6 phrases US viewers type into TikTok search for this topic")
    self_review: Optional[Scorecard] = Field(default=None, description=(
        "Your own honest scoring of the FINAL script (after you fixed its weak spots)"))


class PolicyProblem(BaseModel):
    line: Optional[int] = Field(default=None, description="Index [n] of the narration line, or null")
    issue: str = Field(description="What breaks the rule, in plain words")
    fix: str = Field(description="The exact change that fixes it")


class PolicyCheck(BaseModel):
    passed: bool = Field(description="True when there are no problems")
    tone_ok: bool = Field(description="Fits the channel: educational / motivating, not mean, not fear-mongering")
    graphic_ok: bool = Field(description="Nothing too graphic: no gore, injury detail, self-harm or sexual content")
    policy_ok: bool = Field(description="Nothing against TikTok's Community Guidelines")
    problems: list[PolicyProblem] = Field(default_factory=list)
    summary: str

    def ok(self) -> bool:
        return self.passed and not self.problems


class Idea(BaseModel):
    title: str
    pillar: str
    angle: str = Field(description="One-sentence angle that makes it feel new")
    hook: str = Field(description="Draft hook line, max 9 words")
    summary: str
    key_study: str = Field(description="Researcher · Institution · Year of the core study")
    keywords: list[str]
    interest: int = Field(ge=1, le=10, description="How strongly 16-34 US viewers care")
    search_demand: int = Field(ge=1, le=10, description="How often people search this on TikTok/Google")
    novelty: int = Field(ge=1, le=10, description="How fresh vs. overdone on TikTok")
    evidence_strength: int = Field(ge=1, le=10)


class IdeaBatch(BaseModel):
    ideas: list[Idea]


# ----------------------------------------------------------------- prompts
CRAFT = """\
You write short-form vertical videos (TikTok) that are 65-90 seconds long. Retention craft you always apply:
- Second 0: the hook_line states a surprising payoff or a sharp "you" callout. No intros, no "hey guys", no channel name.
- By second 3 open a curiosity gap the viewer only closes by staying (e.g., "and the reason is not what you think").
- Ask the viewer ONE direct question early (they answer it in their head or in comments).
- Make it personal: a specific, relatable US moment (school, work, Target, Starbucks, group chat, dating apps, rent, $).
- Story beats in plain words; one idea per beat; vary rhythm (short punchy lines between longer ones).
- Name the study on screen right where it is cited (set source_index; the label "→ Researcher · Year" is drawn in code).
- A mid-video twist or "but here's the part nobody tells you" keeps the second half alive.
- Payoff: a satisfying explanation + a practical fix the viewer can try today. Mark that beat flash=true.
- End with loop_line that flows straight back into hook_line so the replay feels seamless.
- Write for the ear: contractions, second person, no lists read aloud, no jargon without a 3-word explanation.
Facts:
- Use only facts that are in the research notes. Never invent researchers, numbers or years.
- Cite a study only from the numbered research SOURCES, and copy its URL exactly into sources[].url.
- Say things plainly and confidently. Do NOT hedge line by line ("might", "reportedly", "I couldn't find",
  "the study didn't look at…") — that kills retention. If a famous effect failed to replicate, that can be the twist.
- Never round a statistic into something false. Correct famous myths when relevant.
- No medical, legal or financial advice beyond general education. 'Spot the trick' videos are framed as protecting
  yourself, never as how to manipulate others.
Visuals: every beat maps to a scene of a minimalist white stick figure on a dark background. You only describe
the drawing (pose, action, simple props). Never ask for text, letters, numbers or logos inside the image — text is added in code.
Give each beat exactly one yellow 'accent' element (the glitch) and exactly one keyword in its on-screen text.
"""


def channel_system(ch: dict) -> str:
    c = ch.get("content") or {}
    pillars = ", ".join(f"{p['name']} ({int(p.get('weight', 0) * 100)}%)" for p in c.get("pillars", [])) or "n/a"
    rules = "\n".join(f"- {r}" for r in c.get("rules", []))
    banned = ", ".join(c.get("banned", [])) or "none"
    return (f"You are the head writer of the TikTok channel \"{ch['name']}\".\n"
            f"Niche: {ch['niche']}\nAbout: {ch.get('description', '')}\n"
            f"Audience: {c.get('audience', 'US, English, ages 16-34')}\nVoice and tone: {c.get('tone', '')}\n"
            f"Content pillars: {pillars}\nBanned topics: {banned}\n{rules}\n\n{CRAFT}")


DEFAULT_WPS = 2.1        # Kokoro, measured: ~230 words came out as 110 s (sentence pauses included)
HARD_FLOOR_S = 61


def word_range(ch: dict) -> tuple[int, int]:
    """Narration words that land the video in the middle of the channel's length range, never under 61 s."""
    wps = float((ch.get("voice") or {}).get("wps") or DEFAULT_WPS)
    min_s, max_s = float(ch.get("min_seconds") or 65), float(ch.get("max_seconds") or 95)
    target = (min_s + max_s) / 2 * wps
    lo = max(round(target * 0.92), math.ceil(max(HARD_FLOOR_S, min_s) * wps))
    hi = max(round(target * 1.08), round(lo * 1.15))
    return lo, hi


def script_problems(script: "Script", ch: dict) -> list[str]:
    """Plain-English problems a code check can see (structure and length). Empty = fine."""
    out = []
    n = len(script.beats)
    if not 8 <= n <= 12:
        out.append(f"Use 8 to 12 beats (now {n}).")
    if script.beats and script.beats[0].kind != "hook":
        out.append("The first beat must be kind 'hook' and start with the hook_line.")
    if script.beats and script.beats[-1].kind != "loop":
        out.append("The last beat must be kind 'loop' and say the loop_line.")
    ids = sorted(sc.id for sc in script.scenes)
    if not 4 <= len(ids) <= 7 or ids != list(range(len(ids))):
        out.append(f"Use 4 to 7 scenes with ids 0..n-1 (now {ids}).")
    bad = sorted({b.scene_id for b in script.beats if b.scene_id not in set(ids)})
    if bad:
        out.append(f"Beats point at scene ids that don't exist: {bad}.")
    lo, hi = word_range(ch)
    wc = word_count(script)
    if not lo <= wc <= hi:
        out.append(f"The narration is {wc} words; it must be {lo}-{hi} words (all beats together).")
    return out


def _norm_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#", 1)[0]
    if "doi.org/" not in u:
        u = u.split("?", 1)[0]
    return u.rstrip("/")


def keep_found_sources(script: "Script", citations: list[dict]) -> "Script":
    """Keep only sources whose URL the research step actually returned; beats citing a dropped one lose the label."""
    found = {_norm_url(c.get("url", "")) for c in citations or []}
    keep, remap = [], {}
    for i, src in enumerate(script.sources):
        if _norm_url(src.url) in found:
            remap[i] = len(keep)
            keep.append(src)
    out = script.model_copy(deep=True)
    out.sources = keep
    ids = {sc.id for sc in out.scenes}
    for b in out.beats:
        if b.source_index is not None:
            b.source_index = remap.get(b.source_index)
        if ids and b.scene_id not in ids:          # small slip: show the first scene instead of failing the video
            b.scene_id = out.scenes[0].id
    return out


def pick_hook_style(ch: dict) -> str:
    strat = ch.get("strategy") or {}
    weights = strat.get("hook_weights") or {}
    styles = (ch.get("content") or {}).get("hook_styles") or ["you-callout", "myth-bust", "number", "question", "pov"]
    w = [max(0.05, float(weights.get(s, 1.0))) for s in styles]
    test = strat.get("test") or {}
    if test.get("variable") == "hook" and test.get("variant") and random.random() < 0.5:
        return test["variant"]
    return random.choices(styles, w)[0]


# ----------------------------------------------------------------- steps
def research_topic(ch: dict, idea: dict, *, video_id=None) -> tuple[dict, float]:
    prompt = f"""Research this video topic and return compact notes for the scriptwriter.
Topic: {idea['title']}
Angle: {idea.get('angle') or ''}
Draft hook: {idea.get('hook') or ''}
Known study hint: {json.dumps(idea.get('sources') or [])}

Give, with the source named next to each fact:
1. The core study: lead author surname, institution, year, what they did, the real key numbers.
2. Two extra facts or real-world examples that make it richer (US-relevant if possible).
3. The popular myth or exaggeration about this topic, so we avoid it (and whether the effect replicated).
4. One practical, evidence-based takeaway the viewer can try today.
5. How US viewers 16-34 talk about or search for this (phrases, relatable moments).
Use about 3-4 searches and stop when you have enough. If you are unsure of a detail, leave it out."""
    text, cites, usd = llm.research(channel_system(ch), prompt, purpose="research", max_searches=4,
                                    channel_id=ch["id"], video_id=video_id)
    return {"notes": text, "citations": cites}, usd


def _sources_block(research: dict) -> str:
    cites = research.get("citations") or []
    return "\n".join(f"[{i}] {c.get('title') or ''} — {c.get('url')}" for i, c in enumerate(cites)) or "(none)"


def write_script(ch: dict, idea: dict, research: dict, *, hook_style: str, feedback: list[str] | None = None,
                 previous: dict | None = None, video_id=None) -> tuple[Script, float]:
    lo, hi = word_range(ch)
    strat = ch.get("strategy") or {}
    fb = ""
    if previous and feedback:
        fb = ("\n\nREWRITE the previous draft below. Fix every point; keep what already works.\n"
              f"Points to fix:\n- " + "\n- ".join(feedback) + f"\n\nPrevious draft JSON:\n{json.dumps(previous)[:12000]}")
    prompt = f"""Write the full script for one video.

Topic: {idea['title']}
Angle: {idea.get('angle') or ''}
Hook style to use: {hook_style}
Channel strategy notes this week: {strat.get('notes', 'none')}

Research notes (ground truth — use only facts supported here):
{research['notes'][:14000]}

Research SOURCES (cite only these; copy the URL exactly):
{_sources_block(research)}

Requirements:
- Total narration (all beats; the hook_line is spoken first, the loop_line last): {lo}-{hi} words.
- 8 to 12 beats. First beat kind='hook' whose narration starts with the hook_line. Last beat kind='loop' whose
  narration is the loop_line.
- 4 to 7 distinct scenes (ids 0..n-1) reused across beats for continuity.
- Each beat: onscreen max 7 words with exactly one 'key' part; one accent; source_index when citing a study.
- hashtags: 3-5, one broad (#psychology/#didyouknow style) plus niche ones.

Before you answer, review your own draft like a ruthless TikTok editor: would a scrolling 20-year-old stop in the
first second? Is the curiosity gap open by second 3? Is there a real "you" moment? Does the loop line flow back into
the hook? Fix the weak spots, then fill self_review honestly for the final version.{fb}"""
    return llm.structured(Script, channel_system(ch), prompt, purpose="script", channel_id=ch["id"],
                          video_id=video_id, max_tokens=20000)


def score_script(ch: dict, script: Script, *, video_id=None) -> tuple[Scorecard, float]:
    prompt = f"""Act as a ruthless TikTok retention editor. Score this script 0-10 on each dimension
(hook = would a scrolling 20-year-old stop in the first second; curiosity_gap; viewer_question; emotional_connection;
clarity; pacing; accuracy_framing; loop; originality vs. the 100 other videos on this topic).
overall = weighted (hook x2, curiosity x1.5, others x1) / 11.5. List concrete, line-level fixes (max 6).

Script JSON:
{script.model_dump_json()}"""
    return llm.structured(Scorecard, channel_system(ch), prompt, purpose="scorecard", effort="medium",
                          channel_id=ch["id"], video_id=video_id, max_tokens=6000)


CHECK_SYSTEM = ("You review short TikTok scripts before they are produced. You only check tone, graphic content and "
                "TikTok's Community Guidelines. You do NOT fact-check: names, places, institutions, years, study "
                "details and citations are out of scope and are never a problem.")


def policy_check(ch: dict, script: Script, *, video_id=None) -> tuple[PolicyCheck, float]:
    """One quick call, no web tools: tone, graphic content, TikTok rules. Facts and citations are not checked."""
    narration = "\n".join(f"[{i}] {b.narration}" for i, b in enumerate(script.beats))
    onscreen = " | ".join(" ".join(p.text for p in b.onscreen) for b in script.beats)
    prompt = f"""Channel: {ch['name']} — {ch.get('niche', '')}. Audience: US, 16-34.

Report a problem ONLY for:
1. Tone that doesn't fit an educational / motivating channel (mean, mocking a group, fear-mongering, preachy).
2. Graphic content: gore, injury or death detail, self-harm, sexual content.
3. TikTok Community Guidelines: dangerous acts or challenges, advice that could harm health or money (e.g. telling
   people to stop medication, guaranteed returns), hate or harassment, content unsafe for minors, misleading claims
   about elections or public health emergencies.
Everyday psychology, studies, numbers and names are fine. If nothing is wrong, passed=true and problems=[].

NARRATION:
{narration}

ON SCREEN: {onscreen}
CAPTION: {script.caption} {' '.join(script.hashtags)}"""
    return llm.structured(PolicyCheck, CHECK_SYSTEM, prompt, purpose="check", channel_id=ch["id"], video_id=video_id,
                          max_tokens=4000)


def length_problem(script: Script, ch: dict) -> str | None:
    """Estimated spoken length below the floor (Creator Rewards needs > 60 s)."""
    wps = float((ch.get("voice") or {}).get("wps") or DEFAULT_WPS)
    floor = max(HARD_FLOOR_S, float(ch.get("min_seconds") or 65))
    est = word_count(script) / wps
    if est < floor:
        lo, _ = word_range(ch)
        return f"The narration is about {est:.0f} seconds; it must be at least {floor:.0f} seconds (about {lo} words)."
    return None


def generate_ideas(ch: dict, existing: list[str], count: int = 12) -> tuple[list[Idea], float]:
    strat = ch.get("strategy") or {}
    research_prompt = f"""Find {count + 6} strong, *evidence-backed* video topics for this channel that US viewers aged
16-34 are curious about right now. Use web search for: trending conversations, frequent TikTok/Google search phrases,
seasonal hooks (today's date matters), and real studies behind each topic. Avoid these already-covered topics:
{json.dumps(existing[-150:])}
Strategy notes from last week's analytics: {strat.get('notes', 'none')}
For each topic give: title, pillar, angle, a draft hook, the key study (Researcher · Institution · Year), search phrases."""
    text, _, usd1 = llm.research(channel_system(ch), research_prompt, purpose="idea_research", max_searches=10,
                                 channel_id=ch["id"])
    batch, usd2 = llm.structured(IdeaBatch, channel_system(ch),
                                 f"Turn these research notes into exactly {count} scored ideas (drop weak or "
                                 f"duplicate ones):\n\n{text[:16000]}", purpose="ideas", effort="medium",
                                 channel_id=ch["id"], max_tokens=12000)
    return batch.ideas, usd1 + usd2


def idea_score(i: Idea, pillar_weights: dict | None = None) -> float:
    w = (pillar_weights or {}).get(i.pillar, 1.0)
    base = i.interest * 0.35 + i.search_demand * 0.25 + i.novelty * 0.2 + i.evidence_strength * 0.2
    return round(base * (0.6 + 0.4 * float(w)), 3)


def spoken_text(script: Script) -> str:
    """Full narration for TTS in beat order."""
    return " ".join(b.narration.strip() for b in script.beats)


def word_count(script: Script) -> int:
    return len(spoken_text(script).split())
