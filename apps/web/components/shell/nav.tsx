"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import {
  LayoutGrid, Tv, Clapperboard, LineChart, FileText, AtSign, Settings, ScrollText, MoreHorizontal, X,
} from "lucide-react";
import * as React from "react";
import { Wordmark } from "@/components/brand";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { cn } from "@/lib/format";

export const NAV = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/channels", label: "Channels", icon: Tv },
  { href: "/videos", label: "Videos", icon: Clapperboard },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/accounts", label: "TikTok accounts", icon: AtSign },
  { href: "/logs", label: "Activity", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
}

export function Sidebar({ worker, email }: { worker: { tone: "good" | "bad" | "neutral"; label: string }; email: string }) {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col border-r border-line bg-bg/80 px-3 py-5 backdrop-blur lg:flex">
      <Link href="/" className="mb-7 rounded-[10px] px-2.5 transition-opacity duration-150 hover:opacity-75" aria-label="Overthought Studio home">
        <Wordmark />
        <span className="mt-0.5 block text-[11px] tracking-wide text-ink-3">studio</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-0.5" aria-label="Main">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex h-9 items-center gap-3 rounded-[9px] px-2.5 text-[14px] transition-colors",
                active ? "text-ink" : "text-ink-3 hover:bg-elev-2/60 hover:text-ink",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-[9px] bg-elev-2"
                  transition={{ type: "spring", stiffness: 520, damping: 42 }}
                />
              )}
              {active && (
                <motion.span layoutId="nav-tick" className="absolute top-2 bottom-2 -left-3 w-[3px] rounded-r-full bg-accent-mark" />
              )}
              <Icon className="relative size-[17px] shrink-0" strokeWidth={1.8} aria-hidden />
              <span className="relative">{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 space-y-3 border-t border-line px-1 pt-4">
        <div className="flex items-center gap-2 px-1.5 text-[12px] text-ink-3">
          <span
            className={cn(
              "size-2 rounded-full",
              worker.tone === "good" ? "bg-good lamp-live" : worker.tone === "bad" ? "bg-bad" : "bg-ink-3",
            )}
            aria-hidden
          />
          <span className="truncate">{worker.label}</span>
        </div>
        <div className="flex items-center justify-between gap-2 px-1">
          <span className="truncate text-[12px] text-ink-3" title={email}>{email}</span>
          <ThemeToggle />
        </div>
        <form action="/auth/signout" method="post">
          <button className="flex h-9 w-full items-center rounded-[9px] px-2.5 text-[13px] text-ink-3 transition-colors hover:bg-elev-2/60 hover:text-ink">Sign out</button>
        </form>
      </div>
    </aside>
  );
}

const MOBILE_PRIMARY = ["/", "/channels", "/videos", "/analytics"];

export function MobileNav({ email }: { email: string }) {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const sheetRef = React.useRef<HTMLDivElement>(null);
  const moreRef = React.useRef<HTMLButtonElement>(null);
  React.useEffect(() => setOpen(false), [pathname]);
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => sheetRef.current?.querySelector<HTMLElement>("a,button")?.focus(), 30);
    const more = moreRef.current;
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      clearTimeout(t);
      more?.focus();
    };
  }, [open]);
  const primary = NAV.filter((n) => MOBILE_PRIMARY.includes(n.href));
  const rest = NAV.filter((n) => !MOBILE_PRIMARY.includes(n.href));
  const restActive = rest.some((n) => isActive(pathname, n.href));
  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-bg/85 px-4 backdrop-blur lg:hidden">
        <Link href="/" aria-label="Overthought Studio home" className="rounded-[8px] transition-opacity duration-150 hover:opacity-75"><Wordmark size="sm" /></Link>
        <ThemeToggle />
      </header>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-bg/92 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
        aria-label="Main"
      >
        {primary.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-16 flex-col items-center justify-center gap-1 text-[11px] transition-colors active:bg-elev-2/60",
                active ? "font-medium text-ink" : "text-ink-3",
              )}>
              {active && <span className="absolute top-0 h-[2px] w-8 rounded-b-full bg-accent-mark" />}
              <Icon className="size-5" strokeWidth={1.8} aria-hidden />
              {label}
            </Link>
          );
        })}
        <button
          ref={moreRef}
          type="button"
          onClick={() => setOpen(true)}
          className={cn(
            "relative flex h-16 flex-col items-center justify-center gap-1 text-[11px] transition-colors active:bg-elev-2/60",
            restActive ? "font-medium text-ink" : "text-ink-3",
          )}
          aria-expanded={open}
          aria-haspopup="dialog"
        >
          {restActive && <span className="absolute top-0 h-[2px] w-8 rounded-b-full bg-accent-mark" />}
          <MoreHorizontal className="size-5" strokeWidth={1.8} aria-hidden />
          More
        </button>
      </nav>
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-black/50"
              onClick={() => setOpen(false)}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            />
            <motion.div
              ref={sheetRef}
              role="dialog"
              aria-modal="true"
              aria-label="More pages"
              initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
              transition={{ type: "spring", stiffness: 520, damping: 44 }}
              className="absolute inset-x-0 bottom-0 rounded-t-[20px] border-t border-line bg-elev px-4 pt-2 pb-[calc(env(safe-area-inset-bottom)+16px)] shadow-[var(--shadow)]"
            >
              <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-line-strong" aria-hidden />
              <div className="mb-3 flex items-center justify-between gap-3">
                <span className="min-w-0 truncate text-[13px] text-ink-3">{email}</span>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close menu"
                  className="-mr-1 flex size-10 shrink-0 items-center justify-center rounded-[10px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink"
                >
                  <X className="size-5" aria-hidden />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {rest.map(({ href, label, icon: Icon }) => {
                  const active = isActive(pathname, href);
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex h-12 items-center gap-3 rounded-[12px] border bg-bg px-3 text-[14px] text-ink transition-colors active:bg-elev-2",
                        active ? "border-line-input font-medium" : "border-line",
                      )}
                    >
                      <Icon className={cn("size-[18px] shrink-0", active ? "text-ink" : "text-ink-3")} strokeWidth={1.8} aria-hidden />
                      <span className="truncate">{label}</span>
                    </Link>
                  );
                })}
              </div>
              <form action="/auth/signout" method="post" className="mt-3">
                <button className="h-11 w-full rounded-[12px] text-[14px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink">Sign out</button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
