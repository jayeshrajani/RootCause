"use client";

import Link from "next/link";
import { LogIn, LogOut, Plus } from "lucide-react";

import { Button, ButtonLink } from "@/components/brand/button";
import { Logo } from "@/components/brand/logo";
import { saveProfile, useProfile } from "@/hooks/use-profile";

function ProfileChip() {
  const profile = useProfile();

  if (profile === undefined) return <span className="h-10 w-24" aria-hidden />;

  if (!profile || profile.kind === "guest") {
    return (
      <ButtonLink href="/auth" variant="ghost">
        <LogIn aria-hidden />
        Sign in
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
        aria-label="Sign out"
      >
        <LogOut aria-hidden />
      </Button>
    </div>
  );
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-forest-900/10 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
        <Logo />
        <div className="flex items-center gap-1.5 sm:gap-2">
          <ProfileChip />
          <ButtonLink href="/report" variant="solid" aria-label="New report">
            <Plus aria-hidden />
            <span className="hidden sm:inline">New report</span>
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
