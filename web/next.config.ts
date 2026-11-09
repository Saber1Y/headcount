import type { NextConfig } from "next";

// Every page is built from the snapshot files at build time, so the site is a
// static export that any static host can serve.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
