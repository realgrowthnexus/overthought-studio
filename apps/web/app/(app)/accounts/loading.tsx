import { SkCard, SkHead, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="accounts">
      <SkHead />
      <SkCard rows={5} />
      <SkCard className="mt-6" rows={1} />
    </SkeletonPage>
  );
}
