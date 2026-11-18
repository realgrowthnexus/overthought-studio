"""Content brain: idea research, script writing, scoring, rewriting, fact-checking."""
from __future__ import annotations

import json
import random
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
    institution: str = Field(description="Short institution name, e.g. 'Notre Dame'")
    year: int
    finding: str = Field(description="The specific finding we rely on, with the real numbers")
    url: str = Field(description="URL of the paper, DOI or a reputable summary")
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


class Claim(BaseModel):
    claim: str
    verdict: Literal["supported", "partly_supported", "unsupported", "contested"]
    evidence: str
    source_url: Optional[str] = None
    fix: Optional[str] = Field(default=None, description="Exact rewrite needed, or null when fine")


class FactCheck(BaseModel):
    claims: list[Claim]
    citations_valid: bool = Field(description="Every on-screen source (researcher, institution, year) is real and correct")
    passes: bool = Field(description="True only if nothing is unsupported and every partly_supported/contested claim is framed honestly")
    required_changes: list[str]
    summary: str


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
- Name the real study on screen as "→ Researcher · Institution · Year" right where it is cited.
- A mid-video twist or "but here's the part nobody tells you" keeps the second half alive.
- Payoff: a satisfying explanation + a practical fix the viewer can try today. Mark that beat flash=true.
- End with loop_line that flows straight back into hook_line so the replay feels seamless.
- Write for the ear: contractions, second person, no lists read aloud, no jargon without a 3-word explanation.
Accuracy is the brand:
- Every factual claim must trace to a real, findable study or reputable source; never invent researchers, numbers or years.
- If an effect failed to replicate or is contested, SAY SO on screen and in narration (that is a hook, not a weakness).
- Never round a statistic into something false ("about 25% noticed" must not become "nobody noticed").
- Correct famous myths when relevant. No medical, legal or financial advice beyond general education.
- 'Spot the trick' videos are framed as protecting yourself, never as how to manipulate others.
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


def _words(min_s: int, max_s: int) -> tuple[int, int]:
    # calm narrator ≈ 2.55 words/second incl. pauses
    return int(min_s * 2.6) + 8, int(max_s * 2.45)


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
    prompt = f"""Research this video topic for our channel and return compact notes for the scriptwriter.
Topic: {idea['title']}
Angle: {idea.get('angle') or ''}
Draft hook: {idea.get('hook') or ''}
Known study hint: {json.dumps(idea.get('sources') or [])}

Find and report, citing sources:
1. The original/most-cited study (lead author surname(s), institution, year, method, sample, exact key numbers).
2. Replication status (replicated / mixed / failed) and any big critiques. Note popular myths about it.
3. 2-3 extra solid findings or real-world examples that make it richer (US-relevant if possible).
4. What exactly US viewers 16-34 search or say about this (phrases, relatable situations).
5. A practical, evidence-based fix or takeaway.
6. Anything that is commonly stated online but is FALSE or exaggerated — so we avoid it.
Be precise with numbers and names. If unsure, say unsure."""
    text, cites, usd = llm.research(channel_system(ch), prompt, purpose="research", max_searches=8,
                                    channel_id=ch["id"], video_id=video_id)
    return {"notes": text, "citations": cites}, usd


def write_script(ch: dict, idea: dict, research: dict, *, hook_style: str, feedback: list[str] | None = None,
                 previous: dict | None = None, video_id=None) -> tuple[Script, float]:
    lo, hi = _words(ch.get("min_seconds", 65), ch.get("max_seconds", 95))
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

Hard requirements:
- Total narration (all beats, including hook_line spoken first and loop_line spoken last) between {lo} and {hi} words,
  so the video lands between {ch.get('min_seconds', 65)} and {ch.get('max_seconds', 95)} seconds. NEVER under {lo} words.
- 8 to 12 beats. First beat kind='hook' whose narration starts with the hook_line. Last beat kind='loop' whose narration is the loop_line.
- 4 to 7 distinct scenes (scene ids 0..n-1) reused across beats for continuity.
- Each beat: onscreen max 7 words with exactly one 'key' part; one accent; source_index set when citing a study.
- sources: only real studies from the research notes; replication field honest.
- hashtags: 3-5, include one broad (#psychology/#didyouknow style) and niche ones.{fb}"""
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


def fact_check(ch: dict, script: Script, *, video_id=None) -> tuple[FactCheck, float]:
    narration = "\n".join(f"[{i}] {b.narration}" for i, b in enumerate(script.beats))
    srcs = "\n".join(f"({i}) {s.researcher} · {s.institution} · {s.year} — {s.finding} — {s.url} [{s.replication}]"
                     for i, s in enumerate(script.sources))
    prompt = f"""Fact-check this TikTok script line by line using web search. Verify every factual claim and every
cited source (does the study exist, is the lead researcher/institution/year right, are numbers stated faithfully,
is replication status honest). Flag rounding that changes meaning, myths, and over-claims.

NARRATION:
{narration}

ON-SCREEN SOURCES:
{srcs}

Write your findings as a clear claim-by-claim review."""
    text, cites, usd1 = llm.research("You are a meticulous science fact-checker for a popular-psychology channel.",
                                     prompt, purpose="factcheck_research", max_searches=10, effort="high",
                                     channel_id=ch["id"], video_id=video_id)
    parse_prompt = f"""Convert this fact-check review into the structured verdict. passes=true only if no claim is
unsupported, citations are valid, and contested items are framed honestly in the script.

REVIEW:
{text[:16000]}

SCRIPT NARRATION:
{narration}"""
    fc, usd2 = llm.structured(FactCheck, "You turn fact-check reviews into strict structured verdicts.", parse_prompt,
                              purpose="factcheck", effort="medium", channel_id=ch["id"], video_id=video_id,
                              max_tokens=8000)
    return fc, usd1 + usd2


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
