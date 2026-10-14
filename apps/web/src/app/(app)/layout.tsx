import { AppHeader } from "@/components/app/app-header";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grain flex min-h-dvh flex-1 flex-col bg-background">
      <AppHeader />
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
