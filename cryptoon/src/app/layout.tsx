// app/layout.tsx
import { Inter } from "next/font/google";
import "../styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from '@/contexts/AuthContext'; // Importe o AuthProvider

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <AuthProvider> {/* Adicione o AuthProvider aqui */}
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            {children}
          </ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}