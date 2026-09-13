import type { NextConfig } from "next";
import examples from "./public/examples/manifest.json";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  agentRules: false,
  output: process.env.LAUNCHPAD_STATIC_EXPORT === "true" ? "export" : undefined,
  trailingSlash: process.env.LAUNCHPAD_STATIC_EXPORT === "true",
  images: {
    unoptimized: process.env.LAUNCHPAD_STATIC_EXPORT === "true",
    localPatterns: [
      { pathname: "/**", search: "" },
      ...Object.entries(examples).map(([mode, sample]) => ({
        pathname: `/examples/${mode}.png`,
        search: `?v=${sample.qa.sha256.slice(0, 12)}`,
      })),
    ],
  },
};

export default nextConfig;
