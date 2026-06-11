import type { Metadata } from "next";

import { Shell } from "../components/console/Shell";
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
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
