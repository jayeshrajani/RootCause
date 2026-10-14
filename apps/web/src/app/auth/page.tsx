import type { Metadata } from "next";

import { ArrowLeft } from "lucide-react";

import { AnimatedLeaf } from "@/components/brand/animated-leaf";
import { BotanicalPattern } from "@/components/brand/botanical";
import { ButtonLink } from "@/components/brand/button";
import { Logo } from "@/components/brand/logo";
import { AuthForm, SkipButton } from "@/components/auth/auth-form";
import { Reveal } from "@/components/motion/reveal";

export const metadata: Metadata = { title: "Sign in" };

export default function AuthPage() {
  return (
    <main className="grid min-h-dvh flex-1 lg:grid-cols-[1fr_1.1fr]">
      <aside className="relative hidden overflow-hidden bg-forest-900 p-10 text-mint-100 lg:flex lg:flex-col">
        <BotanicalPattern className="text-mint-300/[0.06]" />
        <Logo className="relative" />
        <div className="relative flex flex-1 items-center justify-center">
          <AnimatedLeaf className="h-[52vh] max-h-[520px] text-mint-300/80" />
        </div>
        <Reveal delay={0.6} className="relative max-w-sm space-y-3">
          <p className="label-caps text-mint-300/70">Field notes</p>
          <p className="text-2xl leading-snug font-light tracking-tight">
            Built for the field, not the lab. Clear next steps, honest about what we don&apos;t know.
          </p>
        </Reveal>
      </aside>

      <section className="grain flex flex-col bg-mint-50 px-5 py-5 sm:px-10">
        <div className="flex items-center justify-between gap-3">
          <Logo className="lg:hidden" />
          <ButtonLink href="/" variant="ghost" className="-ml-2 hidden lg:inline-flex">
            <ArrowLeft aria-hidden />
            Home
          </ButtonLink>
          <SkipButton />
        </div>
        <div className="flex flex-1 items-center justify-center py-8">
          <Reveal className="flex w-full justify-center">
            <AuthForm />
          </Reveal>
        </div>
      </section>
    </main>
  );
}
