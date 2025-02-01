// src/components/layout/Header.tsx
'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Button } from '../shared/Button';
import { useRouter } from 'next/navigation';

export function Header() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await signOut();
    router.replace('/login');
  };

  return (
    <header className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center">
          <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        </div>
        
        {user && (
          <div className="flex items-center space-x-4">
            <span className="text-gray-700">{user.email}</span>
            <Button onClick={handleLogout} variant="outline">
              Sair
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}