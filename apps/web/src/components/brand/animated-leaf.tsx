"use client";

import { motion } from "motion/react";

import { LEAF_OUTLINE, LEAF_VEINS } from "@/components/brand/botanical";

/** Leaf line-art that draws itself in. */
export function AnimatedLeaf({ className }: { className?: string }) {
  const paths = [LEAF_OUTLINE, "M50 10v190", ...LEAF_VEINS];
  return (
    <svg
      viewBox="-10 -10 120 220"
      fill="none"
      stroke="currentColor"
      strokeWidth={0.6}
      strokeLinecap="round"
      className={className}
      aria-hidden
    >
      {paths.map((d, i) => (
        <motion.path
          key={d}
          d={d}
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{
            pathLength: { duration: i < 2 ? 2.2 : 1.2, delay: i < 2 ? 0.2 : 1 + i * 0.08, ease: [0.65, 0, 0.35, 1] },
            opacity: { duration: 0.3, delay: i < 2 ? 0.2 : 1 + i * 0.08 },
          }}
        />
      ))}
    </svg>
  );
}
