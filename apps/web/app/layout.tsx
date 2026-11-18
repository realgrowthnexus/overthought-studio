import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Providers } from "@/components/providers";
import "./globals.css";

const kalam = localFont({ src: "./fonts/Kalam-Bold.ttf", variable: "--font-kalam", display: "swap", weight: "700" });
const caveatBrush = localFont({ src: "./fonts/CaveatBrush-Regular.ttf", variable: "--font-caveat-brush", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Overthought Studio", template: "%s · Overthought Studio" },
  description: "Runs your TikTok channels: research, scripts, visuals, voice, posting and stats.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#111111" },
    { media: "(prefers-color-scheme: light)", color: "#eeeadf" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} ${kalam.variable} ${caveatBrush.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
