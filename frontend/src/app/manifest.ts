import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "FitSoul AI — Wellness & Nutrition Coach",
    short_name: "FitSoul AI",
    description:
      "Culturally aware Pakistani AI nutritionist, fitness coach, and compassionate wellness companion.",
    start_url: "/",
    display: "standalone",
    background_color: "#fafaf7",
    theme_color: "#0f766e",
    orientation: "portrait",
    icons: [
      {
        src: "/icons/icon-192.svg",
        sizes: "192x192",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.svg",
        sizes: "512x512",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
