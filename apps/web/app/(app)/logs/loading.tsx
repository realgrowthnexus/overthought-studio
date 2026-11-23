import { SkCard, SkHead, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="logs">
      <SkHead />
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]"><SkCard rows={8} /><SkCard rows={4} /></div>
    </SkeletonPage>
  );
}
