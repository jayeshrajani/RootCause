import Link from "next/link";

import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("size-5", className)}
      aria-hidden
    >
      <path d="M12 12.5C12 7 15.4 3.6 20 3c-.4 4.7-3.5 8.1-8 9.5Z" />
      <path d="M12 12.5c0-3.6-2.4-6-5.8-6.6.3 3.3 2.5 5.8 5.8 6.6Z" />
      <path d="M12 12.5V17m0 0-3 4m3-4 3 4m-3-4v4" />
    </svg>
  );
}

export function Logo({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link
      href={href}
      className={cn("inline-flex items-center gap-1.5 text-[15px] font-semibold tracking-[0.08em] uppercase", className)}
    >
      <LogoMark />
      RootCause
    </Link>
  );
}
