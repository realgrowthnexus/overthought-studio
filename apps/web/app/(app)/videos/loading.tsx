"use client";
import { usePathname } from "next/navigation";
import { SkCard, SkChips, SkHead, SkeletonPage } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/primitives";

// Video pages load under this boundary too, so pick the shape from the address being opened.
export default function Loading() {
  const path = usePathname();
  if (path === "/videos") {
    return (
      <SkeletonPage name="videos">
        <SkHead />
        <SkChips n={6} />
        <SkCard rows={8} />
      </SkeletonPage>
    );
  }
  return (
    <SkeletonPage name="video">
      <Skeleton className="mb-2 h-4 w-28" />
      <Skeleton className="mb-6 h-8 w-[min(560px,80vw)]" />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div><Skeleton className="aspect-[9/16] w-full rounded-[14px]" /><Skeleton className="mt-4 h-11 rounded-[10px]" /></div>
        <div className="flex flex-col gap-6"><SkCard className="h-48" /><SkCard rows={6} /></div>
      </div>
    </SkeletonPage>
  );
}
