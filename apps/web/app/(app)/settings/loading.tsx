import { SkCard, SkHead, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="settings">
      <SkHead action />
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]"><SkCard rows={5} /><div className="flex flex-col gap-6"><SkCard rows={3} /><SkCard rows={2} /></div></div>
    </SkeletonPage>
  );
}
