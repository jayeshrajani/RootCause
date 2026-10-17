"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus } from "lucide-react";

import { ButtonLink } from "@/components/brand/button";
import { LanguageSwitcher } from "@/components/app/language-switcher";
import { Logo } from "@/components/brand/logo";
import { useI18n } from "@/lib/i18n";

export function AppHeader() {
  const { t } = useI18n();
  const onReportPage = usePathname() === "/report";
  return (
    <header className="sticky top-0 z-40 border-b border-forest-900/10 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
        <Logo compact />
        <div className="flex items-center gap-1.5 sm:gap-2">
          <LanguageSwitcher />
          {onReportPage ? null : (
            <ButtonLink href="/report" variant="solid" aria-label={t("newReport")} className="size-10 px-0 sm:w-auto sm:px-4">
              <Plus aria-hidden />
              <span className="hidden sm:inline">{t("newReport")}</span>
            </ButtonLink>
          )}
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
