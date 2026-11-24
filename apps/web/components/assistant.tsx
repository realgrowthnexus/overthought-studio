"use client";
import * as React from "react";
import { Bot, Loader2, Send, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import type { AssistantMessage } from "@/lib/data";
import { clearAssistant, loadAssistant, runAssistantAction, sendAssistantMessage } from "@/lib/actions";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/format";

const SUGGESTIONS = [
  "Aaj kya chal raha hai?",
  "RunPod mein kitna balance hai?",
  "Koi video fail hui hai? Kyun?",
  "Agli video kab post hogi?",
];

export function Assistant() {
  const [open, setOpen] = React.useState(false);
  const [msgs, setMsgs] = React.useState<AssistantMessage[]>([]);
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [acting, setActing] = React.useState<string | null>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  // a reply older than 3 minutes is treated as lost (the server marks it so on the next message)
  const waiting = msgs.some((m) => m.status === "pending" && Date.now() - new Date(m.created_at).getTime() < 180_000);

  const refresh = React.useCallback(async () => {
    const r = await loadAssistant();
    if (r.ok && r.data) setMsgs(r.data);
  }, []);

  React.useEffect(() => { if (open) { refresh(); setTimeout(() => inputRef.current?.focus(), 50); } }, [open, refresh]);
  React.useEffect(() => {                                   // poll only while an answer is being written
    if (!open || !waiting) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [open, waiting, refresh]);
  React.useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }); }, [msgs.length, waiting]);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async (q: string) => {
    const t = q.trim();
    if (!t || busy || waiting) return;
    setBusy(true);
    const r = await sendAssistantMessage(t);
    setBusy(false);
    if (!r.ok) { toast.error(r.error); return; }
    setText("");
    refresh();
  };

  const act = async (m: AssistantMessage, i: number) => {
    setActing(`${m.id}:${i}`);
    const r = await runAssistantAction(m.id, i);
    setActing(null);
    if (r.ok) toast.success(r.message ?? "Done."); else toast.error(r.error);
    refresh();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="assistant-panel"
        aria-label={open ? "Close the assistant" : "Open the assistant"}
        className="fixed bottom-[calc(76px+env(safe-area-inset-bottom))] left-4 z-40 inline-flex size-12 items-center justify-center rounded-full bg-accent text-accent-ink shadow-[var(--shadow)] transition-transform hover:scale-105 motion-reduce:transition-none lg:bottom-6 lg:left-[248px]"
      >
        {open ? <X className="size-5" aria-hidden /> : <Bot className="size-5" aria-hidden />}
      </button>

      {open && (
        <section
          id="assistant-panel"
          role="dialog"
          aria-label="Studio assistant"
          className="fixed inset-x-2 bottom-[calc(136px+env(safe-area-inset-bottom))] top-16 z-40 flex flex-col overflow-hidden rounded-[18px] border border-line bg-elev shadow-[var(--shadow)] sm:inset-x-auto sm:left-4 sm:w-[400px] lg:bottom-20 lg:left-[248px] lg:top-auto lg:h-[min(620px,calc(100dvh-120px))]"
        >
          <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-ink">Studio assistant</p>
              <p className="truncate text-[12px] text-ink-3">Knows your studio live. Actions run only when you tap them.</p>
            </div>
            <Button size="sm" variant="ghost" aria-label="Clear the conversation" disabled={!msgs.length || waiting}
              onClick={async () => { const r = await clearAssistant(); if (r.ok) setMsgs([]); }}>
              <Trash2 className="size-4" aria-hidden />
            </Button>
          </header>

          <div ref={listRef} className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4" aria-live="polite">
            {!msgs.length && (
              <div className="flex flex-col gap-2">
                <p className="text-[13px] text-ink-2">Kuch bhi poochiye — balance, videos, errors, schedule. Ya kahiye “Overthought pause karo”.</p>
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" onClick={() => send(s)}
                    className="rounded-[12px] border border-line px-3 py-2 text-left text-[13px] text-ink-2 transition-colors hover:border-line-input hover:text-ink">
                    {s}
                  </button>
                ))}
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id} className={cn("max-w-[88%] rounded-[14px] px-3.5 py-2.5 text-[14px] leading-relaxed",
                m.role === "user" ? "self-end bg-accent/15 text-ink" : "self-start bg-elev-2 text-ink",
                m.status === "error" && "border border-bad/30")}>
                {m.status === "pending" && Date.now() - new Date(m.created_at).getTime() < 180_000 ? (
                  <span className="inline-flex items-center gap-2 text-ink-3"><Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />Soch raha hoon…</span>
                ) : (
                  <p className="whitespace-pre-wrap break-words">{m.content}</p>
                )}
                {m.role === "assistant" && m.actions?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {m.actions.map((a, i) => (
                      <div key={i} className="flex flex-col items-start gap-0.5">
                        <Button size="sm" variant={a.done ? "ghost" : "primary"} disabled={Boolean(a.done)}
                          loading={acting === `${m.id}:${i}`} onClick={() => act(m, i)}>
                          {a.done === "ok" ? "✓ " : ""}{String(a.title ?? a.type)}
                        </Button>
                        {a.label && a.label !== a.title ? <span className="px-1 text-[11px] text-ink-3">{String(a.label)}</span> : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <form className="flex items-end gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <label htmlFor="assistant-input" className="sr-only">Your message</label>
            <textarea
              id="assistant-input" ref={inputRef} rows={1} value={text} maxLength={2000}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
              placeholder={waiting ? "Jawab aa raha hai…" : "Message…"}
              className="max-h-32 min-h-[44px] flex-1 resize-none rounded-[12px] border border-line-input bg-bg px-3 py-2.5 text-[14px] text-ink outline-none placeholder:text-ink-3 focus-visible:border-accent"
            />
            <Button type="submit" variant="primary" aria-label="Send" disabled={!text.trim() || waiting} loading={busy} className="h-[44px]">
              <Send className="size-4" aria-hidden />
            </Button>
          </form>
        </section>
      )}
    </>
  );
}
