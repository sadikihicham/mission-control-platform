import type { Metadata } from "next";
import "./globals.css";
import "./mc.css";
import "./mc-extra.css";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Project Mission Control",
  description: "Cockpit de supervision du développement piloté par IA",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className="dark">
      <body>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
