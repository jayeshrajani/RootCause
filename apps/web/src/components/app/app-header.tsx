"use client";

import Link from "next/link";
import { LogIn, LogOut, Plus } from "lucide-react";

import { Button, ButtonLink } from "@/components/brand/button";
import { LanguageSwitcher } from "@/components/app/language-switcher";
import { Logo } from "@/components/brand/logo";
import { saveProfile, useProfile } from "@/hooks/use-profile";
import { useI18n } from "@/lib/i18n";

function ProfileChip() {
  const profile = useProfile();
  const { t } = useI18n();

  if (profile === undefined) return <span className="h-10 w-24" aria-hidden />;

  if (!profile || profile.kind === "guest") {
    return (
      <ButtonLink href="/auth" variant="ghost" aria-label={t("signIn")}>
        <LogIn aria-hidden />
        <span className="hidden sm:inline">{t("signIn")}</span>
      </ButtonLink>
    );
  }

  return (
    <div className="flex items-center gap-1 rounded-full border border-forest-900/10 bg-white/50 py-1 pr-1 pl-1">
      <span className="flex size-8 items-center justify-center rounded-full bg-forest-900 text-sm font-medium text-mint-100 uppercase">
        {profile.name.charAt(0)}
      </span>
      <span className="hidden max-w-32 truncate px-1.5 text-sm sm:inline">{profile.name}</span>
      <Button
        variant="ghost"
        onClick={() => saveProfile(null)}
        className="size-8 px-0"
        aria-label={t("signOut")}
      >
        <LogOut aria-hidden />
      </Button>
    </div>
  );
}

export function AppHeader() {
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-40 border-b border-forest-900/10 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
        <Logo compact />
        <div className="flex items-center gap-1.5 sm:gap-2">
          <LanguageSwitcher />
          <ProfileChip />
          <ButtonLink href="/report" variant="solid" aria-label={t("newReport")} className="size-10 px-0 sm:w-auto sm:px-4">
            <Plus aria-hidden />
            <span className="hidden sm:inline">{t("newReport")}</span>
          </ButtonLink>
        </div>
      </div>
    </header>
  );
}

export function AppFooterNote() {
  return (
    <p className="mx-auto max-w-5xl px-5 py-8 text-xs text-muted-foreground">
      Triage guidance, not a confirmed diagnosis. Check with a local agricultural expert before
      treating crops. <Link href="/" className="underline underline-offset-2">About RootCause</Link>
    </p>
  );
}
