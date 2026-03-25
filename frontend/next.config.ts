import type { NextConfig } from "next";

/**
 * Em dev, sem NEXT_PUBLIC_API_URL, o browser chama só o Next (3000) e o servidor
 * encaminha /api/* para o FastAPI. Evita NetworkError por host/porta/CORS ao
 * falar com http://localhost:8000 direto do browser.
 *
 * Em produção ou API em outro host: defina NEXT_PUBLIC_API_URL (rewrites desligados).
 * Docker (Next em container): INTERNAL_API_URL=http://nome-do-servico-backend:8000
 */
const internalApiOrigin =
  process.env.INTERNAL_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_URL) {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
