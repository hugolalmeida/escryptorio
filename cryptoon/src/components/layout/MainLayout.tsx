'use client'

import React, { useState } from 'react';
import { Menu, X, Bell, Settings, User, Moon, Sun, LayoutDashboard, FileText } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Avatar } from '@/components/ui/avatar';
import { TooltipProvider, Tooltip } from '@/components/ui/tooltip';
import { useTheme } from 'next-themes';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

const Header = () => {
  const { theme, setTheme } = useTheme();
  
  return (
    <header className="fixed top-0 right-0 left-0 h-16 border-b transition-colors dark:border-gray-800 border-gray-200 z-50 px-4 bg-background">
      <div className="flex items-center justify-between h-full">
        <div className="flex items-center space-x-4">
          <SidebarToggle />
          <h1 className="text-xl font-semibold">Crypto Project</h1>
        </div>
        
        <div className="flex items-center space-x-4">
          <TooltipProvider>
          <Tooltip content="Alternar tema">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              {theme === 'dark' ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </Button>
          </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
          <Tooltip content="Notificações">
            <Button variant="ghost" size="icon">
              <Bell className="h-5 w-5" />
            </Button>
          </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
          <Tooltip content="Configurações">
            <Button variant="ghost" size="icon">
              <Settings className="h-5 w-5" />
            </Button>
          </Tooltip>
          </TooltipProvider>
          <UserMenu />
        </div>
      </div>
    </header>
  );
};

// Sidebar Component
const Sidebar = ({ isOpen }: { isOpen: boolean }) => {
  const menuItems = [
    { label: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
    { label: 'Contratos', href: '/dashboard/contract', icon: <FileText className="w-4 h-4" />},
    { label: 'Chaves', href: '/dashboard/keys' },
    { label: 'Logs', href: '/dashboard/logs' },
    { label: 'Crypto', href: '/dashboard/crypto' },
    { label: 'Histórico', href: '/dashboard/history' },
  ];

  return (
    <aside 
      className={`fixed left-0 top-16 h-[calc(100vh-4rem)] border-r transition-colors dark:border-gray-800 border-gray-200 bg-background transition-all duration-300 ${
        isOpen ? 'w-64' : 'w-20'
      }`}
    >
      <nav className="p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.href}>
              <a
                href={item.href}
                className="flex items-center p-2 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                {/* Você pode adicionar ícones aqui */}
                <span className={`${!isOpen && 'hidden'} ml-3`}>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
};

// Layout Component
const Layout = ({ children }: { children: React.ReactNode }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar isOpen={isSidebarOpen} />
      <main className={`pt-16 ${isSidebarOpen ? 'ml-64' : 'ml-20'} transition-all duration-300 p-6`}>
        {children}
      </main>
    </div>
  );
};

// Componentes auxiliares
const SidebarToggle = () => {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Button variant="ghost" size="icon" onClick={() => setIsOpen(!isOpen)}>
      {isOpen ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
    </Button>
  );
};

const UserMenu = () => {
  const { user, signOut } = useAuth();
    const router = useRouter();

  const handleLogout = async () => {
    await signOut();
    router.replace('/login');
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-8 w-8 rounded-full">
          <Avatar className="h-8 w-8">
            <User className="h-4 w-4" />
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem>Perfil</DropdownMenuItem>
        <DropdownMenuItem>Configurações</DropdownMenuItem>
        <DropdownMenuItem onClick={handleLogout} variant="outline">Sair</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export { Header, Sidebar, Layout };