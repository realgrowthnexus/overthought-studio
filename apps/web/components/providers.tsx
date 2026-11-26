"use client";
import { ThemeProvider, useTheme } from "next-themes";
import { Toaster } from "sonner";
import { MotionConfig } from "motion/react";

function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="top-right"
      toastOptions={{
        style: {
          background: "var(--bg-elev)",
          color: "var(--ink)",
          border: "1px solid var(--line)",
          borderRadius: "12px",
          fontSize: "13px",
        },
      }}
    />
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <MotionConfig reducedMotion="user">
        <div className="relative z-[1]">{children}</div>
        <ThemedToaster />
      </MotionConfig>
    </ThemeProvider>
  );
}
