"use client";

import { useId, type ComponentProps, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";

import { cn } from "@/lib/utils";

export const inputClass =
  "h-13 w-full rounded-2xl border border-forest-900/15 bg-white/80 px-4 text-base text-forest-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] outline-none transition-[border-color,box-shadow,background-color] duration-200 placeholder:text-forest-900/35 hover:border-forest-900/30 focus:border-forest-700 focus:bg-white focus:ring-4 focus:ring-mint-300/70 aria-invalid:border-destructive aria-invalid:ring-destructive/15";

export function FieldMessage({ id, message }: { id: string; message?: string }) {
  return (
    <AnimatePresence initial={false}>
      {message ? (
        <motion.p
          id={id}
          role="alert"
          className="text-sm text-destructive"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25 }}
        >
          {message}
        </motion.p>
      ) : null}
    </AnimatePresence>
  );
}

interface TextFieldProps extends ComponentProps<"input"> {
  label: ReactNode;
  error?: string;
  hint?: ReactNode;
  trailing?: ReactNode;
}

export function TextField({ label, error, hint, trailing, className, id, ...props }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="block text-sm font-medium text-forest-900">
        {label}
      </label>
      <div className="relative">
        <input
          id={inputId}
          aria-invalid={!!error || undefined}
          aria-describedby={cn(hint && hintId, error && errorId) || undefined}
          className={cn(inputClass, trailing && "pr-12", className)}
          {...props}
        />
        {trailing ? <div className="absolute inset-y-0 right-1.5 flex items-center">{trailing}</div> : null}
      </div>
      {hint ? (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      <FieldMessage id={errorId} message={error} />
    </div>
  );
}
