import { requireAdminPage } from "@/lib/auth";
import { getServices, getSettings, getWorkers } from "@/lib/data";
import { Sidebar, MobileNav } from "@/components/shell/nav";
import { ServiceAlertBar } from "@/components/services";
import { relTime } from "@/lib/format";

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
      <Sidebar worker={worker} email={admin.email} />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav email={admin.email} />
        <ServiceAlertBar initial={services} paused={settings.paused} />
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 pt-6 pb-28 sm:px-8 sm:pt-8 lg:pb-12">{children}</main>
      </div>
    </div>
  );
}
