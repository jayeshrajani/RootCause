"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/brand/button";
import { pillClass, PillIcon } from "@/components/brand/pill";
import { TextField } from "@/components/forms/text-field";
import { Spinner } from "@/components/ui/spinner";
import { saveProfile } from "@/hooks/use-profile";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

type Mode = "signin" | "signup";

const schema = z
  .object({
    mode: z.enum(["signin", "signup"]),
    name: z.string().trim(),
    email: z.email("Enter a valid email address"),
    password: z.string().min(8, "Use at least 8 characters"),
  })
  .refine((v) => v.mode === "signin" || v.name.length >= 2, {
    path: ["name"],
    message: "Tell us what to call you",
  });

type AuthValues = z.infer<typeof schema>;

const NEXT_ROUTE = "/report";

export function SkipButton() {
  const router = useRouter();
  const { t } = useI18n();
  return (
    <Button
      variant="outline"
      onClick={() => {
        saveProfile({ kind: "guest" });
        router.push(NEXT_ROUTE);
      }}
    >
      {t("skipForNow")}
      <ArrowRight className="transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Button>
  );
}

export function AuthAsideCopy() {
  const { t } = useI18n();
  return (
    <div className="relative max-w-sm space-y-3">
      <p className="label-caps text-mint-300/70">{t("fieldNotes")}</p>
      <p className="text-2xl leading-snug font-light tracking-tight">{t("authAside")}</p>
    </div>
  );
}

export function AuthForm() {
  const router = useRouter();
  const { t } = useI18n();
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    setValue,
    control,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<AuthValues>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "signin", name: "", email: "", password: "" },
  });
  const mode = useWatch({ control, name: "mode" });
  const copy = mode === "signin"
    ? { title: t("welcomeBack"), subtitle: t("signInSubtitle"), submit: t("signIn") }
    : { title: t("createAccount"), subtitle: t("signUpSubtitle"), submit: t("createAccountAction") };

  const switchMode = (next: Mode) => {
    setValue("mode", next);
    clearErrors();
  };

  const skip = () => {
    saveProfile({ kind: "guest" });
    router.push(NEXT_ROUTE);
  };

  const onSubmit = handleSubmit(({ mode: m, name, email }) => {
    const displayName = m === "signup" ? name : email.split("@")[0] ?? email;
    saveProfile({ kind: "member", name: displayName, email });
    router.push(NEXT_ROUTE);
  });

  return (
    <div className="w-full max-w-md">
      <LayoutGroup>
        <div
          role="tablist"
          aria-label="Account"
          className="relative mb-8 grid grid-cols-2 rounded-full bg-forest-900/[0.06] p-1"
        >
          {(["signin", "signup"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => switchMode(m)}
              className={cn(
                "relative h-10 rounded-full text-sm font-medium transition-colors",
                mode === m ? "text-mint-100" : "text-forest-900/60 hover:text-forest-900",
              )}
            >
              {mode === m ? (
                <motion.span
                  layoutId="auth-tab"
                  className="absolute inset-0 rounded-full bg-forest-900"
                  transition={{ type: "spring", stiffness: 420, damping: 36 }}
                />
              ) : null}
              <span className="relative">{m === "signin" ? t("signIn") : t("signUp")}</span>
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="mb-8"
          >
            <h1 className="text-4xl font-medium tracking-[-0.03em]">{copy.title}</h1>
            <p className="mt-2 text-muted-foreground">{copy.subtitle}</p>
          </motion.div>
        </AnimatePresence>

        <motion.form layout onSubmit={onSubmit} noValidate className="space-y-5">
          <AnimatePresence initial={false}>
            {mode === "signup" ? (
              <motion.div
                key="name"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.35 }}
                className="overflow-hidden"
              >
                <TextField
                  label={t("yourName")}
                  autoComplete="name"
                  placeholder="e.g. Asha Patil"
                  error={errors.name?.message}
                  {...register("name")}
                />
              </motion.div>
            ) : null}
          </AnimatePresence>

          <motion.div layout>
            <TextField
              label={t("email")}
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="you@example.com"
              error={errors.email?.message}
              {...register("email")}
            />
          </motion.div>

          <motion.div layout>
            <TextField
              label={t("password")}
              type={showPassword ? "text" : "password"}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              placeholder={t("passwordHint")}
              error={errors.password?.message}
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="flex size-10 items-center justify-center rounded-xl text-forest-900/50 transition-colors hover:bg-mint-100 hover:text-forest-900"
                  aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              }
              {...register("password")}
            />
          </motion.div>

          <motion.div layout className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className={pillClass("dark", "h-13 w-full justify-between")}
            >
              {copy.submit}
              <PillIcon>
                {isSubmitting ? <Spinner className="size-4" /> : <ArrowRight className="size-4" />}
              </PillIcon>
            </button>
          </motion.div>
        </motion.form>
      </LayoutGroup>

      <div className="my-8 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        {t("or")}
        <span className="h-px flex-1 bg-border" />
      </div>

      <button
        type="button"
        onClick={skip}
        className="h-12 w-full rounded-full border border-forest-900/15 text-[15px] font-medium transition-colors hover:border-forest-900/40 hover:bg-white/60"
      >
        {t("continueGuest")}
      </button>

      <p className="mt-6 text-center text-xs leading-relaxed text-muted-foreground">
        {t("accountPreview")}
      </p>
    </div>
  );
}
