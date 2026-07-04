export function resolveApiUrl(url: string): string {
  if (typeof window === 'undefined') return url;
  const pageHost = window.location.hostname;
  if (pageHost && pageHost !== 'localhost' && pageHost !== '127.0.0.1') {
    return url
      .replace('://localhost:', `://${pageHost}:`)
      .replace('://127.0.0.1:', `://${pageHost}:`);
  }
  return url;
}
