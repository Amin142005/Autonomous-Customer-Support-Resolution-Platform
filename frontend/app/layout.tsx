import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LoginGate } from "@/components/layout/LoginGate";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "CloudDesk Support Console",
  description: "Autonomous customer support and resolution platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <LoginGate>
            <AppShell>{children}</AppShell>
          </LoginGate>
        </AuthProvider>
      </body>
    </html>
  );
}
