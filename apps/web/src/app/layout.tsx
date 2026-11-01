import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = { title: "CryptoLab · Pesquisa de mercado", description: "Workspace privado de inteligência e pesquisa de estratégias Bybit Spot.", robots: { index: false, follow: false } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body><a href="#main-content" className="skip-link">Pular para o conteúdo</a><Shell>{children}</Shell></body></html>;
}
