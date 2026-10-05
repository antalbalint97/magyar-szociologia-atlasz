import type { MetadataRoute } from "next";

// Pilot deployment: no crawler should index the atlas yet.
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", disallow: "/" }] };
}
