import type { Metadata, Viewport } from "next";
import { Geist_Mono, Noto_Sans_Devanagari, Noto_Sans_Gurmukhi, Outfit } from "next/font/google";

import { MotionProvider } from "@/components/motion/motion-provider";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

const outfit = Outfit({ variable: "--font-outfit", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const devanagari = Noto_Sans_Devanagari({ variable: "--font-devanagari", subsets: ["devanagari", "latin"] });
const gurmukhi = Noto_Sans_Gurmukhi({ variable: "--font-gurmukhi", subsets: ["gurmukhi", "latin"] });

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
    <html lang="en" className={`${outfit.variable} ${geistMono.variable} ${devanagari.variable} ${gurmukhi.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <I18nProvider>
          <MotionProvider>{children}</MotionProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
