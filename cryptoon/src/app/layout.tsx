'use client'

import { Inter } from "next/font/google";
import "../styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from '@/contexts/AuthContext';
import { Layout } from '@/components/layout/MainLayout';
import { usePathname } from 'next/navigation';

const inter = Inter({ subsets: ["latin"] });

// Lista de rotas públicas que não devem mostrar o layout principal
const publicRoutes = ['/login', '/auth/sign-in', '/auth/sign-up'];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname();
  const isPublicRoute = publicRoutes.includes(pathname);

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <AuthProvider>
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            {isPublicRoute ? (
              children
            ) : (
              <Layout>{children}</Layout>
            )}
          </ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}