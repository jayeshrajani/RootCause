"use client";

import { Fragment, type ReactNode } from "react";
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
  /** Words on their own line after `text`, revealed with a highlighter sweep styled by `accentClassName`. */
  accent?: string;
  accentClassName?: string;
  as?: "h1" | "h2" | "p";
  className?: string;
  delay?: number;
  stagger?: number;
}

/** Word-by-word masked rise. Screen readers get the plain sentence. */
export function RevealText({
  text,
  accent,
  accentClassName,
  as: Tag = "h1",
  className,
  delay = 0,
  stagger = 0.06,
}: RevealTextProps) {
  const lead = text.split(" ");
  const words = accent ? [...lead, ...accent.split(" ")] : lead;
  const sweepDelay = delay + words.length * stagger + 0.45;
  return (
    <Tag className={className} aria-label={accent ? `${text} ${accent}` : text}>
      {words.map((word, i) => {
        const content = (
          <>
            {word}
            {i < words.length - 1 ? "\u00a0" : null}
          </>
        );
        return (
          <Fragment key={`${word}-${i}`}>
          {accent && i === lead.length ? <br /> : null}
          <span
            aria-hidden
            className="-mt-[0.25em] -mb-[0.12em] inline-block overflow-hidden pt-[0.25em] pb-[0.2em] align-bottom"
          >
            <motion.span
              className="inline-block"
              initial={{ y: "160%" }}
              animate={{ y: "0%" }}
              transition={{ duration: 1, ease: EASE, delay: delay + i * stagger }}
            >
              {i < lead.length ? (
                content
              ) : (
                <motion.span
                  className={accentClassName}
                  initial={{ backgroundSize: "0% 100%" }}
                  animate={{ backgroundSize: "100% 100%" }}
                  transition={{
                    duration: 0.45,
                    ease: "easeOut",
                    delay: sweepDelay + (i - lead.length) * 0.3,
                  }}
                >
                  {content}
                </motion.span>
              )}
            </motion.span>
          </span>
          </Fragment>
        );
      })}
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
