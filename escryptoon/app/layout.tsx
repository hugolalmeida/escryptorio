import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../styles/globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: "Escritorio Crypto",
  description: "Projeto de Advocacia da empresa ....",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>
        <div style={{ display: 'flex', minHeight: '100vh' }}>
          <Sidebar />
          <main style={{ flex: 1, marginLeft: '250px' }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
