import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type Variant = "solid" | "outline" | "ghost";
type Size = "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  solid: "bg-forest-900 text-mint-100 hover:bg-forest-800",
  outline:
    "border border-forest-900/20 bg-white/45 text-forest-900 backdrop-blur-sm hover:border-forest-900/40 hover:bg-white/80",
  ghost: "text-forest-900/70 hover:bg-forest-900/[0.06] hover:text-forest-900",
};

const SIZES: Record<Size, string> = {
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-12 gap-2.5 px-5 text-[15px]",
};

export function buttonClass(variant: Variant = "outline", size: Size = "md", className?: string) {
  return cn(
    "group inline-flex shrink-0 items-center justify-center rounded-full font-medium whitespace-nowrap transition-[background-color,border-color,color,transform] duration-200 outline-none focus-visible:ring-3 focus-visible:ring-forest-500/40 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}

type Common = { variant?: Variant; size?: Size };

export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: Common & ComponentProps<typeof Link>) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

export function Button({
  variant,
  size,
  className,
  type = "button",
  ...props
}: Common & ComponentProps<"button">) {
  return <button type={type} className={buttonClass(variant, size, className)} {...props} />;
}
