import { SkCard, SkHead, SkStats, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="overview">
      <SkHead />
      <SkStats />
      <SkCard className="mt-6 h-64" />
      <div className="mt-6 grid gap-6 lg:grid-cols-2"><SkCard rows={3} /><SkCard rows={3} /></div>
    </SkeletonPage>
  );
}
