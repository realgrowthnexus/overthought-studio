"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check, SendHorizontal, X } from "lucide-react";
import { toast } from "sonner";
import { browserClient } from "@/lib/supabase/browser";
import { askAssistant, loadAssistant, runAssistantAction, type AssistantState } from "@/lib/assistant-actions";
import { cn } from "@/lib/format";

const SUGGESTIONS = [
  "Studio ka haal kya hai?",
  "Koi video ruki hui hai? Kyun?",
  "Agli video kab post hogi?",
  "Is mahine RunPod pe kitna kharcha hua?",
];

/** The assistant's face, drawn in code so it looks the same on every phone (an emoji font would not).
 *  It blinks now and then; while a reply is on its way the mouth turns into a little "o". */
function Face({ size = 48, thinking = false, still = false }: { size?: number; thinking?: boolean; still?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden className="block">
      <circle cx="24" cy="24" r="23" fill="var(--accent)" />
      <circle cx="24" cy="24" r="22.25" fill="none" stroke="var(--accent-ink)" strokeOpacity="0.18" strokeWidth="1.5" />
      <g className={still ? undefined : "face-blink"} style={{ transformOrigin: "24px 19px" }}>
        <ellipse cx="17" cy="19" rx="2.6" ry="3.4" fill="var(--accent-ink)" />
        <ellipse cx="31" cy="19" rx="2.6" ry="3.4" fill="var(--accent-ink)" />
      </g>
      <circle cx="12.5" cy="27" r="2.8" fill="#ff7a59" fillOpacity="0.45" />
      <circle cx="35.5" cy="27" r="2.8" fill="#ff7a59" fillOpacity="0.45" />
      {thinking
        ? <ellipse cx="24" cy="32" rx="3" ry="3.4" fill="var(--accent-ink)" />
        : <path d="M15.5 29.5 Q24 38 32.5 29.5" fill="none" stroke="var(--accent-ink)" strokeWidth="2.8" strokeLinecap="round" />}
    </svg>
  );
}

export function Assistant() {
  const [open, setOpen] = React.useState(false);
  const [state, setState] = React.useState<AssistantState | null>(null);
  const [text, setText] = React.useState("");
  const [sending, startSend] = React.useTransition();
  const [busyAction, setBusyAction] = React.useState<string | null>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  const router = useRouter();
  const reduce = useReducedMotion();
  const titleId = React.useId();

  const refresh = React.useCallback(async () => {
    const r = await loadAssistant();
    if (r.ok && r.data) setState(r.data);
  }, []);

  // live updates while the panel is open: the worker writes the reply into assistant_messages
  React.useEffect(() => {
    if (!open) return;
    void refresh();
    const supabase = browserClient();
    const ch = supabase.channel(`assistant:${Math.random().toString(36).slice(2, 8)}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "assistant_messages" }, () => void refresh())
      .subscribe();
    const poll = setInterval(() => void refresh(), 15_000);      // safety net if realtime drops
    return () => {
      clearInterval(poll);
      supabase.removeChannel(ch);
    };
  }, [open, refresh]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    const t = setTimeout(() => inputRef.current?.focus(), 60);
    const btn = buttonRef.current;
    return () => {
      document.removeEventListener("keydown", onKey);
      clearTimeout(t);
      btn?.focus();
    };
  }, [open]);

  const messages = state?.messages ?? [];
  const waiting = messages.some((m) => m.status === "pending");
  React.useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages.length, waiting, reduce]);

  const send = (q: string) => {
    const v = q.trim();
    if (!v || waiting || sending) return;
    startSend(async () => {
      const r = await askAssistant(v);
      if (!r.ok) { toast.error(r.error); return; }
      setText("");
      await refresh();
    });
  };

  const click = async (messageId: number, i: number) => {
    const key = `${messageId}:${i}`;
    setBusyAction(key);
    try {
      const r = await runAssistantAction(messageId, i);
      if (r.ok) toast.success(r.message ?? "Done.");
      else toast.error(r.error);
      await refresh();
      router.refresh();
    } finally {
      setBusyAction(null);
    }
  };

  const blocked = state && !state.signedIn;
  const limitLabel = state?.limitedUntil
    ? new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", weekday: "short" }).format(new Date(state.limitedUntil))
    : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="assistant-panel"
        aria-label={open ? "Close assistant" : "Open assistant"}
        className={cn(
          "fixed z-40 flex size-14 items-center justify-center rounded-full shadow-[var(--shadow)] transition-transform hover:-translate-y-0.5 hover:scale-105 active:scale-95 motion-reduce:transition-none motion-reduce:hover:transform-none",
          "right-4 bottom-[calc(env(safe-area-inset-bottom)+76px)] lg:right-6 lg:bottom-6",
        )}
      >
        <Face size={56} thinking={waiting} still={Boolean(reduce)} />
        {open && (
          <span className="absolute -top-1 -right-1 flex size-6 items-center justify-center rounded-full border border-line bg-elev text-ink shadow-[var(--shadow)]">
            <X className="size-3.5" aria-hidden />
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/30 lg:hidden"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              aria-hidden
            />
            <motion.section
              id="assistant-panel"
              role="dialog"
              aria-modal="false"
              aria-labelledby={titleId}
              initial={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className={cn(
                "fixed z-50 flex flex-col overflow-hidden border border-line bg-elev shadow-[var(--shadow)]",
                "inset-x-0 bottom-0 h-[85dvh] rounded-t-[20px] pb-[env(safe-area-inset-bottom)]",
                "lg:inset-x-auto lg:bottom-24 lg:right-6 lg:h-[min(620px,calc(100dvh-120px))] lg:w-[400px] lg:rounded-[18px] lg:pb-0",
              )}
            >
              <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
                <div className="flex min-w-0 items-center gap-2">
                  <Face size={26} thinking={waiting} still />
                  <h2 id={titleId} className="truncate text-[15px] font-semibold text-ink">Assistant</h2>
                </div>
                <button type="button" onClick={() => setOpen(false)} aria-label="Close assistant" className="tap flex size-9 items-center justify-center rounded-[9px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink">
                  <X className="size-4" aria-hidden />
                </button>
              </header>

              <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
                {!state && <p className="text-[13px] text-ink-3">Loading…</p>}
                {blocked && (
                  <div className="rounded-[12px] border border-line bg-bg p-3 text-[13px] text-ink-2">
                    Claude isn&apos;t signed in, so the assistant can&apos;t answer yet.{" "}
                    <Link href="/settings#claude" className="font-medium text-ink underline decoration-accent-mark decoration-2 underline-offset-4" onClick={() => setOpen(false)}>Open Settings</Link>
                  </div>
                )}
                {state && !blocked && messages.length === 0 && (
                  <div className="flex flex-col gap-3">
                    <p className="text-[13px] text-ink-2">
                      Ask me anything about the studio: videos, jobs, errors, money, the schedule. If something needs doing, I&apos;ll show a button. Nothing happens until you click it.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {SUGGESTIONS.map((s) => (
                        <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line bg-bg px-3 py-1.5 text-left text-[12.5px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink">
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <ol className="flex flex-col gap-3">
                  {messages.map((m) => (
                    <li key={m.id} className={cn("flex flex-col gap-2", m.role === "user" ? "items-end" : "items-start")}>
                      {m.status === "pending" ? (
                        <div className="flex items-center gap-1.5 rounded-[14px] bg-elev-2 px-3 py-2.5" role="status" aria-label="Assistant is typing">
                          {[0, 1, 2].map((i) => (
                            <span key={i} className={cn("size-1.5 rounded-full bg-ink-3", !reduce && "animate-pulse")} style={{ animationDelay: `${i * 150}ms` }} />
                          ))}
                        </div>
                      ) : (
                        <p className={cn(
                          "max-w-[88%] rounded-[14px] px-3 py-2 text-[13.5px] leading-relaxed whitespace-pre-wrap break-words",
                          m.role === "user" ? "bg-accent-soft text-ink" : m.status === "error" ? "border border-bad/30 bg-bad-soft text-ink" : "bg-elev-2 text-ink",
                        )}>
                          {m.content}
                        </p>
                      )}
                      {m.actions?.length > 0 && (
                        <div className="flex max-w-[88%] flex-wrap gap-2">
                          {m.actions.map((a, i) => (
                            <button
                              key={i}
                              type="button"
                              disabled={a.done || busyAction !== null}
                              onClick={() => click(m.id, i)}
                              className={cn(
                                "inline-flex min-h-9 items-center gap-1.5 rounded-[10px] border px-3 py-1.5 text-[13px] font-medium transition-colors",
                                a.done ? "border-line text-ink-3" : "border-accent/60 bg-bg text-ink hover:bg-accent-soft",
                              )}
                            >
                              {a.done && <Check className="size-3.5 text-good" aria-hidden />}
                              {busyAction === `${m.id}:${i}` ? "Working…" : a.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              </div>

              <form
                className="border-t border-line p-3"
                onSubmit={(e) => { e.preventDefault(); send(text); }}
              >
                {limitLabel && (
                  <p className="mb-2 text-[12px] text-warn">Claude&apos;s limit is in force until about {limitLabel}. Replies wait until then.</p>
                )}
                <div className="flex items-end gap-2">
                  <label htmlFor="assistant-input" className="sr-only">Message the assistant</label>
                  <textarea
                    id="assistant-input"
                    ref={inputRef}
                    rows={1}
                    value={text}
                    maxLength={2000}
                    disabled={Boolean(blocked) || waiting}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); }
                    }}
                    placeholder={waiting ? "Answering…" : "Kuch bhi poochiye…"}
                    className="max-h-32 min-h-10 flex-1 resize-none rounded-[10px] border border-line-input bg-bg px-3 py-2 text-[14px] text-ink placeholder:text-ink-3 focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-60"
                  />
                  <button
                    type="submit"
                    disabled={!text.trim() || waiting || sending || Boolean(blocked)}
                    aria-label="Send"
                    className="tap flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-accent text-accent-ink transition-colors hover:bg-accent-hover"
                  >
                    <SendHorizontal className="size-4" aria-hidden />
                  </button>
                </div>
              </form>
            </motion.section>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
