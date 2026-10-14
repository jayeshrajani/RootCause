import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

type Tone = "dark" | "light";

const toneClass: Record<Tone, { root: string; icon: string }> = {
  dark: {
    root: "bg-forest-900 text-mint-100 hover:bg-forest-800",
    icon: "bg-mint-300 text-forest-900",
  },
  light: {
    root: "bg-mint-100 text-forest-900 hover:bg-white",
    icon: "bg-forest-900 text-mint-100",
  },
};

export function pillClass(tone: Tone = "dark", className?: string) {
  return cn(
    "group inline-flex h-12 items-center gap-4 rounded-full pr-1.5 pl-6 text-[15px] font-medium transition-colors duration-300 outline-none focus-visible:ring-3 focus-visible:ring-forest-500/50 disabled:pointer-events-none disabled:opacity-60",
    toneClass[tone].root,
    className,
  );
}

export function PillIcon({ tone = "dark", children }: { tone?: Tone; children?: ReactNode }) {
  return (
    <span
      className={cn(
        "flex size-9 items-center justify-center rounded-full transition-transform duration-500 ease-out-expo",
        children ? "group-hover:translate-x-0.5" : "group-hover:rotate-45",
        toneClass[tone].icon,
      )}
      aria-hidden
    >
      {children ?? <ArrowUpRight className="size-4" />}
    </span>
  );
}

export function PillLink({
  tone = "dark",
  className,
  children,
  ...props
}: { tone?: Tone } & ComponentProps<typeof Link>) {
  return (
    <Link className={pillClass(tone, className)} {...props}>
      {children}
      <PillIcon tone={tone} />
    </Link>
  );
}
