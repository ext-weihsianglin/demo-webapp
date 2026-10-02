import type { NextConfig } from 'next';
const config: NextConfig = {
  // A whole-page draft can take longer than Next's default 30-second proxy limit.
  experimental: { proxyTimeout: 300_000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.API_URL || 'http://127.0.0.1:8000'}/api/:path*` }];
  },
};
export default config;
