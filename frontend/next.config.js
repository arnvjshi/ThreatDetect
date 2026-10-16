/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backend = process.env.INTERNAL_BACKEND_URL || 'http://backend:8000';
    return [
      {
        source: '/clips/:path*',
        destination: `${backend}/clips/:path*`,
      },
      {
        source: '/thumbnails/:path*',
        destination: `${backend}/thumbnails/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
