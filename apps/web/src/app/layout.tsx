import type { Metadata, Viewport } from "next";
import { Geist_Mono, Outfit } from "next/font/google";

import { MotionProvider } from "@/components/motion/motion-provider";
import "./globals.css";

const outfit = Outfit({ variable: "--font-outfit", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "RootCause · Crop distress triage", template: "%s · RootCause" },
  description:
    "Report a struggling crop with photos and symptoms. RootCause separates observations from hypotheses, rates urgency and suggests safe next steps.",
};

export const viewport: Viewport = {
  themeColor: "#163626",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${outfit.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
