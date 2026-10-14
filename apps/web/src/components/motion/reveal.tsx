"use client";

import type { ReactNode } from "react";
import { motion, type HTMLMotionProps } from "motion/react";

const EASE = [0.16, 1, 0.3, 1] as const;

interface RevealProps extends HTMLMotionProps<"div"> {
  delay?: number;
  y?: number;
  /** Animate when scrolled into view instead of on mount. */
  onView?: boolean;
}

export function Reveal({ delay = 0, y = 18, onView = false, children, ...props }: RevealProps) {
  const target = { opacity: 1, y: 0, filter: "blur(0px)" };
  return (
    <motion.div
      initial={{ opacity: 0, y, filter: "blur(6px)" }}
      {...(onView
        ? { whileInView: target, viewport: { once: true, margin: "-60px" } }
        : { animate: target })}
      transition={{ duration: 0.9, ease: EASE, delay }}
      {...props}
    >
      {children}
    </motion.div>
  );
}

interface RevealTextProps {
  text: string;
  as?: "h1" | "h2" | "p";
  className?: string;
  delay?: number;
  stagger?: number;
}

/** Word-by-word masked rise. Screen readers get the plain sentence. */
export function RevealText({
  text,
  as: Tag = "h1",
  className,
  delay = 0,
  stagger = 0.06,
}: RevealTextProps) {
  const words = text.split(" ");
  return (
    <Tag className={className} aria-label={text}>
      {words.map((word, i) => (
        <span
          key={`${word}-${i}`}
          aria-hidden
          className="inline-block overflow-hidden pb-[0.08em] align-bottom"
        >
          <motion.span
            className="inline-block"
            initial={{ y: "105%" }}
            animate={{ y: "0%" }}
            transition={{ duration: 1, ease: EASE, delay: delay + i * stagger }}
          >
            {word}
            {i < words.length - 1 ? "\u00a0" : null}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}

export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }}
    >
      {children}
    </motion.div>
  );
}

export const staggerItem = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.8, ease: EASE } },
};

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={staggerItem} className={className}>
      {children}
    </motion.div>
  );
}
