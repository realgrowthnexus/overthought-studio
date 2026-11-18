import type { Metadata } from "next";
import { getChannels, getReports } from "@/lib/data";
import { PageHeader, Panel } from "@/components/ui/primitives";
import { EmptyState } from "@/components/ui/empty";
import { ReportCard } from "@/components/report-card";
import { JobButton } from "@/components/job-button";

export const metadata: Metadata = { title: "Reports" };
export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const [reports, channels] = await Promise.all([getReports(), getChannels()]);
  return (
    <>
      <PageHeader
        title="Weekly reports"
        description="Every Monday the studio compares the week against each channel's median, keeps what worked, retires what didn't, and picks one thing to test."
        actions={<JobButton type="weekly_review" payload={{}}>Run a review now</JobButton>}
      />
      {reports.length === 0 ? (
        <Panel>
          <EmptyState title="No reports yet">The first one arrives the Monday after your first week of posts.</EmptyState>
        </Panel>
      ) : (
        <div className="flex max-w-[860px] flex-col gap-4">
          {reports.map((r, i) => (
            <ReportCard key={r.id} report={r} defaultOpen={i === 0} channelName={channels.find((c) => c.id === r.channel_id)?.name ?? "All channels"} />
          ))}
        </div>
      )}
    </>
  );
}
