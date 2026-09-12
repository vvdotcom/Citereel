import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";

import "./preline.css";
import "./styles.css";

const inter = localFont({
  src: "../../assets/InterVariable.ttf",
  display: "swap",
  weight: "100 900",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Citereel — Evidence-backed product videos",
  description:
    "Turn product websites into evidence-backed videos with Citereel. Research, storyboard, record and narrate with AWS-powered agents.",
  applicationName: "Citereel",
  icons: { icon: { url: "/brand/citereel.svg", type: "image/svg+xml" } },
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={inter.variable}>{children}</body>
    </html>
  );
}
