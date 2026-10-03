const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export function getToken() { return localStorage.getItem("diet_token"); }
export function setToken(token) { if (token) localStorage.setItem("diet_token", token); }
export function clearToken() { localStorage.removeItem("diet_token"); }
export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}
