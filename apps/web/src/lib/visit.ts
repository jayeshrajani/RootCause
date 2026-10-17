// One "visit" is a browser session: session cookies (no expiry) are shared across tabs and
// cleared when the browser closes. The API enforces the same allowance per visit id.
export const INVESTIGATION_LIMIT = 5;
export const VISIT_HEADER = "X-RootCause-Session";

const ID_COOKIE = "rc_visit";
const COUNT_COOKIE = "rc_investigations";

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

function writeCookie(name: string, value: string): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax`;
}

export function visitId(): string {
  let id = readCookie(ID_COOKIE);
  if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
    id = crypto.randomUUID();
    writeCookie(ID_COOKIE, id);
  }
  return id;
}

export function investigationsUsed(): number {
  const used = Number(readCookie(COUNT_COOKIE));
  return Number.isInteger(used) && used > 0 ? used : 0;
}

export function investigationsLeft(): number {
  return Math.max(0, INVESTIGATION_LIMIT - investigationsUsed());
}

export function recordInvestigation(): void {
  writeCookie(COUNT_COOKIE, String(investigationsUsed() + 1));
}

/** The API said this visit is out of investigations; keep the browser in step. */
export function markLimitReached(): void {
  writeCookie(COUNT_COOKIE, String(INVESTIGATION_LIMIT));
}
