import type { ChannelStyle } from "@/lib/types";

/** Free Kokoro voices (run on the VPS). Keep in sync with worker/studio/voice.py CATALOG. */
export const VOICES: { id: string; label: string }[] = [
  { id: "am_michael+am_fenrir", label: "Male · deep, warm" },
  { id: "am_fenrir", label: "Male · deep" },
  { id: "am_michael", label: "Male · clear" },
  { id: "am_onyx", label: "Male · low, calm" },
  { id: "am_puck", label: "Male · energetic" },
  { id: "bm_george", label: "Male · British storyteller" },
  { id: "af_heart", label: "Female · warm" },
  { id: "af_bella", label: "Female · confident" },
  { id: "af_kore", label: "Female · calm, deep" },
  { id: "af_aoede", label: "Female · soft" },
  { id: "bf_emma", label: "Female · British" },
  { id: "af_heart+af_bella", label: "Female · rich blend" },
];
export const DEFAULT_VOICE = "am_michael+am_fenrir";
export const voiceSample = (id: string) => `/voices/${id.replace("+", "_")}.mp3`;

const FIGURE =
  "classic stick figure made of single thin white lines: circle head, one straight line body, two line arms, two line legs, on pure black background, flat minimal hand-drawn vector, monochrome white lines only, no shading, no text, no letters";

export const STYLE_PRESETS: { id: string; name: string; description: string; style: ChannelStyle }[] = [
  {
    id: "charcoal",
    name: "Charcoal",
    description: "The Overthought look: white figure on soft charcoal, one yellow accent.",
    style: { preset: "charcoal", bg: "#111111", ink: "#F6F1E6", accent: "#FFD60A", body_font: "Kalam-Bold.ttf", key_font: "CaveatBrush-Regular.ttf", figure_prompt: FIGURE, seed: 7 },
  },
  {
    id: "midnight-green",
    name: "Midnight money",
    description: "Deep green-black with a mint accent. Suits money and decision topics.",
    style: { preset: "midnight-green", bg: "#0F1412", ink: "#EEF3EC", accent: "#4BE3A0", body_font: "Kalam-Bold.ttf", key_font: "CaveatBrush-Regular.ttf", figure_prompt: FIGURE, seed: 11 },
  },
  {
    id: "ember",
    name: "Ember",
    description: "Warm black with an ember-red accent. Suits history and true stories.",
    style: { preset: "ember", bg: "#14100E", ink: "#F3E9DC", accent: "#FF6B3D", body_font: "Kalam-Bold.ttf", key_font: "CaveatBrush-Regular.ttf", figure_prompt: FIGURE, seed: 19 },
  },
  {
    id: "blueprint",
    name: "Blueprint night",
    description: "Ink-blue black with a cyan accent. Suits science and how-things-work.",
    style: { preset: "blueprint", bg: "#0E1218", ink: "#E8EEF6", accent: "#38C6FF", body_font: "Kalam-Bold.ttf", key_font: "CaveatBrush-Regular.ttf", figure_prompt: FIGURE, seed: 23 },
  },
  {
    id: "noir-red",
    name: "Noir stamp",
    description: "Pure charcoal with a stamp-red accent. Suits myth-busting.",
    style: { preset: "noir-red", bg: "#121212", ink: "#F2F0EC", accent: "#FF4D5E", body_font: "Kalam-Bold.ttf", key_font: "CaveatBrush-Regular.ttf", figure_prompt: FIGURE, seed: 31 },
  },
];

export const HOOK_STYLES = [
  { id: "you-callout", label: "You-callout", example: "You've done this today and didn't notice." },
  { id: "myth-bust", label: "Myth bust", example: "Everything you learned about this is wrong." },
  { id: "number", label: "Number shock", example: "Only 1 in 4 people saw it." },
  { id: "question", label: "Question", example: "Why do you forget why you walked in?" },
  { id: "pov", label: "POV", example: "POV: your brain at 2 a.m." },
  { id: "story", label: "Story cold-open", example: "In 1999, two researchers filmed a gorilla…" },
];

export const TIMEZONES = ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"];
