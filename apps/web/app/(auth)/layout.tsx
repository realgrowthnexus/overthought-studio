import Link from "next/link";
import { StickFigure, Wordmark } from "@/components/brand";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid grid-cols-1 [&>*]:min-w-0 min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      {/* always the dark brand panel: the `dark` class re-scopes the tokens so the wordmark and figure stay off-white in light mode */}
      <section className="dark relative hidden overflow-hidden border-r border-line bg-bg text-ink lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(700px 480px at 50% 45%, rgb(246 241 230 / 0.07), transparent 70%)" }}
          aria-hidden
        />
        <Wordmark className="relative" />
        <div className="relative mx-auto flex flex-col items-center">
          <StickFigure className="h-64 w-56" />
          <p className="mt-6 max-w-[30ch] text-center font-hand text-[22px] leading-snug">
            why your brain does that.
            <br />
            <span className="text-accent-text">real studies, tiny stick figures.</span>
          </p>
        </div>
        <p className="relative text-[12px] text-ink-3">
          Overthought Studio runs research, scripts, drawing, voice and posting for your channels.
        </p>
      </section>
      <section className="flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-[380px]">
          <div className="mb-8 lg:hidden"><Wordmark size="lg" /></div>
          {children}
        </div>
        <nav className="mt-8 flex gap-2 text-[13px] text-ink-3" aria-label="Legal">
          <Link href="/privacy" className="inline-flex h-10 items-center rounded-[8px] px-2 transition-colors hover:text-ink">Privacy</Link>
          <Link href="/terms" className="inline-flex h-10 items-center rounded-[8px] px-2 transition-colors hover:text-ink">Terms</Link>
        </nav>
      </section>
    </main>
  );
}
