"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

/** Opening the app always starts on the landing screen. Phones reopen the last tab's URL
 * (often /results, whose data lived in that old tab), so a fresh page load of any inner page
 * goes home. Navigation inside the app is unaffected: this root layout mounts once per load. */
export function EntryGuard() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/") router.replace("/");
    // Only the route the page was loaded on matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
