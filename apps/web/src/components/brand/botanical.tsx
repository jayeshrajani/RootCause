import { cn } from "@/lib/utils";

const VEINS = [
  { y: 38, l: 15 },
  { y: 60, l: 23 },
  { y: 84, l: 27 },
  { y: 108, l: 26 },
  { y: 130, l: 20 },
  { y: 150, l: 12 },
];

export const LEAF_OUTLINE =
  "M50 4C82 30 92 80 76 128c-10 28-20 40-26 48-6-8-16-20-26-48C8 80 18 30 50 4Z";
export const LEAF_VEINS = VEINS.flatMap(({ y, l }) => [
  `M50 ${y}q${l * 0.6} -6 ${l} ${-l * 0.7}`,
  `M50 ${y}q${-l * 0.6} -6 ${-l} ${-l * 0.7}`,
]);

function Leaf({ transform }: { transform: string }) {
  return (
    <g transform={transform}>
      <path d={LEAF_OUTLINE} />
      <path d="M50 10v190" />
      {LEAF_VEINS.map((d) => (
        <path key={d} d={d} />
      ))}
    </g>
  );
}

const LEAVES = [
  "translate(40 420) rotate(-28) scale(1.9)",
  "translate(250 80) rotate(18) scale(1.2)",
  "translate(520 520) rotate(-62) scale(1.5)",
  "translate(760 40) rotate(34) scale(2.1)",
  "translate(980 430) rotate(-14) scale(1.4)",
  "translate(1180 110) rotate(52) scale(1.1)",
  "translate(1300 520) rotate(-40) scale(1.8)",
  "translate(380 300) rotate(80) scale(0.8)",
  "translate(880 290) rotate(-90) scale(0.9)",
];

/** Decorative line-art leaves; purely visual. */
export function BotanicalPattern({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1440 800"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      stroke="currentColor"
      strokeWidth={1}
      className={cn("pointer-events-none absolute inset-0 size-full", className)}
      aria-hidden
    >
      {LEAVES.map((t) => (
        <Leaf key={t} transform={t} />
      ))}
    </svg>
  );
}

export function LeafIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="-10 -10 120 220"
      fill="none"
      stroke="currentColor"
      strokeWidth={0.8}
      strokeLinecap="round"
      className={className}
      aria-hidden
    >
      <Leaf transform="" />
    </svg>
  );
}
