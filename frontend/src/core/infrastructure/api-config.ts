/**
 * Base URL da API no browser.
 * - Sem NEXT_PUBLIC_API_URL: string vazia → fetch em `/api/...` (proxy via next.config rewrites).
 * - Com NEXT_PUBLIC_API_URL: URL absoluta do backend (produção ou API remota).
 */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
