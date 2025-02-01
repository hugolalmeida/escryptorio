// src/components/auth/AccessDenied.tsx
'use client';

import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

export const AccessDenied = () => {
  const { user } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md text-center">
        <h1 className="text-3xl font-bold text-red-600 mb-4">Acesso Negado</h1>
        <p className="mb-4">
          {user 
            ? "Você não tem permissão para acessar esta página." 
            : "Você precisa estar logado para acessar esta página."
          }
        </p>
        <div className="flex justify-center space-x-4">
          <Link 
            href="/dashboard" 
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
          >
            Ir para Dashboard
          </Link>
          {!user && (
            <Link 
              href="/login" 
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
            >
              Fazer Login
            </Link>
          )}
        </div>
      </div>
    </div>
  );
};