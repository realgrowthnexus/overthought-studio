import { SkCard, SkHead, SkeletonPage } from "@/components/skeletons";

export default function Loading() {
  return (
    <SkeletonPage name="reports">
      <SkHead action />
      <SkCard rows={4} />
    </SkeletonPage>
  );
}
