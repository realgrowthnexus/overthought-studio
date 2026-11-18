"use client";
import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/format";

export function Switch({
  checked, onCheckedChange, disabled, label, id, size = "md",
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
  id?: string;
  size?: "md" | "lg";
}) {
  const w = size === "lg" ? "w-12 h-7" : "w-10 h-6";
  const knob = size === "lg" ? 22 : 18;
  const travel = size === "lg" ? 20 : 16;
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "tap relative inline-flex shrink-0 cursor-pointer items-center rounded-full border p-[2px] transition-colors duration-200",
        w,
        checked ? "border-transparent bg-accent" : "border-line-input bg-elev-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      <motion.span
        className={cn("block rounded-full shadow-sm", checked ? "bg-accent-ink" : "bg-ink-3")}
        style={{ width: knob, height: knob }}
        animate={{ x: checked ? travel : 0 }}
        transition={{ type: "spring", stiffness: 600, damping: 36 }}
      />
    </button>
  );
}
