/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: [],
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  // Enable for PWA
  async headers() {
    return [
      {
        source: '/api/stream',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-cache, no-transform',
          },
          {
            key: 'Connection',
            value: 'keep-alive',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
