const base = (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8011/v1").replace(
  /\/$/,
  "",
);

export function apiEndpoint(path: string) {
  return `${base}/${path.replace(/^\//, "")}`;
}

export const apiFetch = (path: string, init?: RequestInit) =>
  fetch(apiEndpoint(path), { credentials: "include", ...init });
