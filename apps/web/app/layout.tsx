import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "CommerceFlow Agent",
  description: "受控电商售后 Agent 运营控制台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
      </body>
    </html>
  );
}
