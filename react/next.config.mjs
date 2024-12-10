/** @type {import('next').NextConfig} */
const nextConfig = {
    eslint: {
        ignoreDuringBuilds: true,
    },
    logging: {
        fetches: {
            fullUrl: true
        }
    },
    basePath: `${process.env.NEXT_PUBLIC_BASE_PATH}`,
    trailingSlash: true
};

export default nextConfig;
