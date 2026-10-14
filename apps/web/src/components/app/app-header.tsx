"use client";

import Link from "next/link";
import { LogOut } from "lucide-react";

import { BracketLink, Logo } from "@/components/brand/logo";
import { saveProfile, useProfile } from "@/hooks/use-profile";

function ProfileChip() {
  const profile = useProfile();

  if (profile === undefined) return <span className="h-9 w-24" aria-hidden />;

  if (!profile || profile.kind === "guest") {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden rounded-full bg-forest-900/[0.06] px-3 py-1.5 text-xs text-forest-700 sm:inline">
          Guest
        </span>
        <BracketLink href="/auth">Sign in</BracketLink>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="flex size-9 items-center justify-center rounded-full bg-forest-900 text-sm font-medium text-mint-100 uppercase">
        {profile.name.charAt(0)}
      </span>
      <span className="hidden max-w-32 truncate text-sm sm:inline">{profile.name}</span>
      <button
        type="button"
        onClick={() => saveProfile(null)}
        className="flex size-9 items-center justify-center rounded-full text-forest-900/50 transition-colors hover:bg-forest-900/5 hover:text-forest-900"
        aria-label="Sign out"
      >
        <LogOut className="size-4" />
      </button>
    </div>
  );
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-forest-900/10 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-5">
        <Logo />
        <div className="flex items-center gap-2 sm:gap-6">
          <BracketLink href="/report" className="hidden sm:inline-flex">
            New report
          </BracketLink>
          <ProfileChip />
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
