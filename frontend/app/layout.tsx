import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Defense AI",
  description: "AI-powered daily project defense and engineering evaluation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
