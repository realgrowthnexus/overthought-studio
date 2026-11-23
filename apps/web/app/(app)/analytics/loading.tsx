import { SkCard, SkChips, SkHead, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="analytics">
      <SkHead />
      <SkChips n={4} />
      <SkCard className="h-80" />
      <SkCard className="mt-6" rows={5} />
    </SkeletonPage>
  );
}
