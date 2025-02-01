// src/components/auth/ProtectedRoute.tsx
'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Role } from '@/types/auth';
import { useRouter } from 'next/navigation';
import React, { ReactNode, useEffect } from 'react';

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: Role[];
  redirectPath?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles = ['BASIC', 'PREMIUM', 'ADMIN'],
  redirectPath = '/login'
}) => {
  const { user, loading, initialized } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (initialized && !loading && !user) {
      router.replace(redirectPath);
    }
  }, [user, loading, initialized, router, redirectPath]);

  // Mostra loading apenas durante a inicialização
  if (!initialized || loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  // Se não há usuário, retorna null (o redirect acontecerá pelo useEffect)
  if (!user) return null;

  // Verificação de roles
  if (allowedRoles && user.profile && !allowedRoles.includes(user.profile.role)) {
    router.replace('/dashboard');
    return null;
  }

  return <>{children}</>;
};