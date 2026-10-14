// Stable per-file blob URLs so previews keep their identity across re-renders and steps.
const cache = new WeakMap<File, string>();

export function objectUrlFor(file: File): string {
  let url = cache.get(file);
  if (!url) {
    url = URL.createObjectURL(file);
    cache.set(file, url);
  }
  return url;
}

export function releaseObjectUrl(file: File): void {
  const url = cache.get(file);
  if (url) {
    URL.revokeObjectURL(url);
    cache.delete(file);
  }
}
