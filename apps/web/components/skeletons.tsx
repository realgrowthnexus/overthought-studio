import { Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/format";

/** Page-shaped loading states. Each route's loading.tsx composes these to mirror its real layout. */
export function SkeletonPage({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-busy="true" data-skeleton={name}>
      <span className="sr-only">Loading…</span>
      {children}
    </div>
  );
}

export function SkHead({ action = false, sub = true }: { action?: boolean; sub?: boolean }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <Skeleton className="h-8 w-44" />
        {sub && <Skeleton className="mt-3 h-4 w-72 max-w-[70vw]" />}
      </div>
      {action && <Skeleton className="h-10 w-32 rounded-[10px]" />}
    </div>
  );
}

export function SkChips({ n = 5 }: { n?: number }) {
  return (
    <div className="mb-5 flex gap-2 overflow-hidden">
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-9 w-24 shrink-0 rounded-full" />)}
    </div>
  );
}

export function SkCard({ className, rows = 0 }: { className?: string; rows?: number }) {
  return (
    <div className={cn("rounded-[14px] border border-line bg-elev p-5", className)}>
      <Skeleton className="h-5 w-36" />
      <Skeleton className="mt-2 h-3.5 w-56 max-w-full" />
      {rows > 0 && (
        <div className="mt-5 flex flex-col gap-4">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-6 w-20 rounded-full" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SkStats({ n = 4 }: { n?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4 [&>*]:min-w-0">
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-28 rounded-[14px]" />)}
    </div>
  );
}
