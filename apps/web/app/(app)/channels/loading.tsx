"use client";
import { usePathname } from "next/navigation";
import { SkCard, SkHead, SkeletonPage } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/primitives";

// The channel layout loads under this boundary too, so pick the shape from the address being opened.
export default function Loading() {
  const path = usePathname();
  if (path === "/channels" || path === "/channels/new") {
    return (
      <SkeletonPage name="channels">
        <SkHead action />
        <SkCard rows={5} />
      </SkeletonPage>
    );
  }
  return (
    <SkeletonPage name="channel">
      <Skeleton className="mb-3 h-4 w-20" />
      <Skeleton className="h-8 w-56" />
      <Skeleton className="mt-3 h-4 w-80 max-w-[75vw]" />
      <div className="mt-5 flex gap-2"><Skeleton className="h-10 w-40 rounded-[10px]" /><Skeleton className="h-10 w-36 rounded-[10px]" /></div>
      <div className="mt-6 mb-6 flex gap-4 border-b border-line pb-3">
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-4 w-16" />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]"><SkCard className="h-80" /><SkCard rows={5} /></div>
    </SkeletonPage>
  );
}
