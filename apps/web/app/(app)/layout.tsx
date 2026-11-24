import { requireAdminPage } from "@/lib/auth";
import { getServices, getSettings, getWorkers } from "@/lib/data";
import { Sidebar, MobileNav } from "@/components/shell/nav";
import { ServiceAlertBar } from "@/components/services";
import { relTime } from "@/lib/format";
import { Assistant } from "@/components/assistant";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const admin = await requireAdminPage();
  const [services, settings, workers] = await Promise.all([getServices(), getSettings(), getWorkers()]);
  const latest = workers[0];
  const age = latest ? Date.now() - new Date(latest.last_seen).getTime() : Infinity;
  const worker =
    !latest ? { tone: "neutral" as const, label: "Worker not installed yet" }
    : age < 3 * 60_000 ? { tone: "good" as const, label: `Worker online · ${latest.worker_id}` }
    : { tone: "bad" as const, label: `Worker last seen ${relTime(latest.last_seen)}` };

  return (
    <div className="flex min-h-dvh">
      <a
        href="#main"
        className="fixed top-3 left-3 z-[60] -translate-y-20 rounded-[10px] bg-accent px-4 py-2.5 text-[14px] font-medium text-accent-ink shadow-[var(--shadow)] transition-transform focus-visible:translate-y-0"
      >
        Skip to content
      </a>
      <Sidebar worker={worker} email={admin.email} />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav email={admin.email} />
        <ServiceAlertBar initial={services} paused={settings.paused} />
        <Assistant />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1280px] flex-1 px-4 pt-6 pb-28 outline-none sm:px-8 sm:pt-8 lg:pb-12">{children}</main>
      </div>
    </div>
  );
}
