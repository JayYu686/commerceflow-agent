import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "CommerceFlow Agent",
  description: "Controlled after-sales Agent console",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

