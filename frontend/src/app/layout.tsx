import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { AppShell } from "@/components/layout/AppShell";
import { ServiceWorkerRegistrar } from "@/components/pwa/ServiceWorkerRegistrar";

import "./globals.css";

export const metadata: Metadata = {
  title: "FitSoul AI — Nutrition & Wellness Coach",
  description:
    "24/7 Pakistani AI nutritionist, fitness coach, and compassionate wellness companion.",
  applicationName: "FitSoul AI",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "FitSoul AI",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f766e",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <ServiceWorkerRegistrar />
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
