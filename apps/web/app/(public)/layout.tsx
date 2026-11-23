import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { ThemeToggle } from "@/components/shell/theme-toggle";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-[860px] items-center justify-between gap-4 px-4 py-4 sm:px-6 sm:py-6">
        <Link href="/" aria-label="Overthought Studio" className="rounded-[8px] transition-opacity duration-150 hover:opacity-75"><Wordmark size="sm" /></Link>
        <nav className="flex items-center gap-1 text-[13px] text-ink-3" aria-label="Legal">
          <Link href="/privacy" className="inline-flex h-10 items-center rounded-[8px] px-2.5 transition-colors hover:text-ink">Privacy</Link>
          <Link href="/terms" className="inline-flex h-10 items-center rounded-[8px] px-2.5 transition-colors hover:text-ink">Terms</Link>
          <ThemeToggle />
        </nav>
      </header>
      <main className="mx-auto max-w-[860px] px-4 pt-4 pb-24 sm:px-6 sm:pt-6">{children}</main>
    </div>
  );
}
