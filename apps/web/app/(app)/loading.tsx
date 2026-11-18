import { Skeleton } from "@/components/ui/primitives";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton className="mb-2 h-8 w-56" />
      <Skeleton className="mb-8 h-4 w-80" />
      <div className="grid grid-cols-1 [&>*]:min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-[14px]" />)}
      </div>
      <Skeleton className="mt-6 h-72 rounded-[14px]" />
    </div>
  );
}
