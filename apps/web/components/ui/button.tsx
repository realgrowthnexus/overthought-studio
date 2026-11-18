import * as React from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "quiet";
type Size = "sm" | "md" | "lg" | "icon";

const base =
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none " +
  "transition-[background-color,color,border-color,box-shadow,transform] duration-150 ease-[var(--ease-out-soft)] " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-50 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]";

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-ink hover:bg-accent-hover shadow-[inset_0_-2px_0_rgb(0_0_0/0.12)] " +
    "disabled:bg-elev-2 disabled:text-ink-3 disabled:shadow-none disabled:opacity-100 " +
    "disabled:aria-busy:bg-accent disabled:aria-busy:text-accent-ink disabled:aria-busy:opacity-80",
  secondary:
    "bg-elev text-ink border border-line hover:border-line-strong hover:bg-elev-2",
  ghost: "text-ink-2 hover:text-ink hover:bg-elev-2",
  quiet: "text-ink-3 hover:text-ink",
  danger:
    "bg-bad-soft text-bad border border-transparent hover:border-bad/40",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] rounded-[8px]",
  md: "h-10 px-4 text-sm rounded-[10px]",
  lg: "h-12 px-5 text-[15px] rounded-[12px]",
  icon: "h-10 w-10 rounded-[10px]",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(base, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

export function ButtonLink({
  href, variant = "secondary", size = "md", className, children, prefetch, ...rest
}: { href: string; variant?: Variant; size?: Size; className?: string; children: React.ReactNode; prefetch?: boolean } &
  Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  const external = href.startsWith("http");
  if (href.startsWith("/api/")) {
    // full navigation for route handlers (OAuth redirects)
    return (
      <a href={href} className={cn(base, variants[variant], sizes[size], className)} {...rest}>
        {children}
      </a>
    );
  }
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cn(base, variants[variant], sizes[size], className)} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <Link href={href} prefetch={prefetch} className={cn(base, variants[variant], sizes[size], className)} {...rest}>
      {children}
    </Link>
  );
}
