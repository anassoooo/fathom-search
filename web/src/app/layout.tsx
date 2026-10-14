import { Toaster } from "@/components/ui/sonner";
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/components/auth-provider";
import { ThemeProvider } from "next-themes";

const plex = IBM_Plex_Sans({
  variable: "--font-plex",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz"],
});

export const metadata: Metadata = {
  title: "Fathom: product search that understands the request",
  description:
    "Search 35,736 products by describing what you want or showing a photo. Hybrid retrieval, reranking, and LLM query understanding.",
};

export const viewport: Viewport = {
  themeColor: "#f5f8f7",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${plex.variable} ${newsreader.variable}`}>
        <ThemeProvider attribute="data-theme" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
          <AuthProvider>
            {children}
            <Toaster />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
