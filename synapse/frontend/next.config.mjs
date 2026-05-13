/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow cross-origin requests from Replit dev preview domains
  allowedDevOrigins: ['*.spock.replit.dev', '*.replit.dev', '*.repl.co'],
  // Transpile ESM-only packages so Next.js / webpack can bundle them correctly.
  transpilePackages: [
    'react-markdown',
    'rehype-raw',
    'rehype-katex',
    'remark-gfm',
    'remark-math',
    'unified',
    'bail',
    'is-plain-obj',
    'trough',
    'vfile',
    'unist-util-stringify-position',
    'mdast-util-from-markdown',
    'mdast-util-to-string',
    'micromark',
  ],
  // Skip trailing-slash redirect so /api/v1/* proxy rewrites run first.
  skipTrailingSlashRedirect: true,
  // Proxy /api/v1/* → Django backend
  async rewrites() {
    const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      .replace(/\/api\/v1\/?$/, '')
      .replace(/\/$/, '');
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*/`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Cross-Origin-Opener-Policy', value: 'unsafe-none' },
        ],
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'avatars.githubusercontent.com' },
      { protocol: 'https', hostname: 'github.com' },
      { protocol: 'https', hostname: 'img.youtube.com' },
      { protocol: 'https', hostname: 'i.ytimg.com' },
    ],
    formats: ['image/avif', 'image/webp'],
  },
  experimental: {
    optimizePackageImports: [
      'framer-motion',
      'recharts',
      '@radix-ui/react-dialog',
      '@tanstack/react-query',
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  compress: true,
  productionBrowserSourceMaps: false,
  reactStrictMode: false,
  // Only use standalone output when not in Replit dev
  ...(process.env.NODE_ENV === 'production' && !process.env.REPL_ID
    ? { output: 'standalone' }
    : {}),
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production'
      ? { exclude: ['error', 'warn'] }
      : false,
  },
  // Ignore TypeScript and ESLint errors during dev to show the app
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  webpack(config, { isServer }) {
    if (!isServer) {
      config.optimization.splitChunks = {
        ...config.optimization.splitChunks,
        cacheGroups: {
          ...(config.optimization.splitChunks?.cacheGroups ?? {}),
          recharts: {
            test: /[\\/]node_modules[\\/]recharts[\\/]/,
            name: 'recharts',
            chunks: 'all',
            priority: 30,
          },
          framerMotion: {
            test: /[\\/]node_modules[\\/]framer-motion[\\/]/,
            name: 'framer-motion',
            chunks: 'all',
            priority: 29,
          },
          markdown: {
            test: /[\\/]node_modules[\\/](react-markdown|remark|rehype|micromark|katex)[\\/]/,
            name: 'markdown',
            chunks: 'all',
            priority: 28,
          },
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            chunks: 'all',
            priority: 10,
            reuseExistingChunk: true,
          },
        },
      };
    }
    return config;
  },
}

export default nextConfig
