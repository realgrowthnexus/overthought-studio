import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { ThemeToggle } from "@/components/shell/theme-toggle";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-[860px] items-center justify-between px-6 py-6">
        <Link href="/" aria-label="Overthought Studio"><Wordmark size="sm" /></Link>
        <nav className="flex items-center gap-4 text-[13px] text-ink-3">
          <Link href="/privacy" className="hover:text-ink">Privacy</Link>
          <Link href="/terms" className="hover:text-ink">Terms</Link>
          <ThemeToggle />
        </nav>
      </header>
      <main className="mx-auto max-w-[860px] px-6 pt-6 pb-24">{children}</main>
    </div>
  );
}
