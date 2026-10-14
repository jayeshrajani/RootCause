"use client";

import type { ReactNode } from "react";
import { motion } from "motion/react";
import { Check, Plus } from "lucide-react";

import { cn } from "@/lib/utils";

interface ChipProps {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  icon?: boolean;
  size?: "sm" | "md";
}

export function Chip({ active, onClick, children, icon = true, size = "md" }: ChipProps) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border transition-colors duration-200",
        size === "md" ? "h-10 px-4 text-sm" : "h-9 px-3.5 text-[13px]",
        active
          ? "border-forest-900 bg-forest-900 text-mint-100"
          : "border-forest-900/15 bg-white/70 text-forest-900 hover:border-forest-900/40",
      )}
    >
      {icon ? (
        active ? (
          <Check className="size-3.5" aria-hidden />
        ) : (
          <Plus className="size-3.5 opacity-50" aria-hidden />
        )
      ) : null}
      {children}
    </motion.button>
  );
}
