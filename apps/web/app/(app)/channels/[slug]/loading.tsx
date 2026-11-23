import { SkCard, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="channel">
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <SkCard className="h-80" />
        <SkCard rows={5} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]"><SkCard rows={4} /><SkCard rows={3} /></div>
    </SkeletonPage>
  );
}
