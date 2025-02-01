// src/app/login/page.tsx
'use client';

import { SignInForm } from '@/components/auth/SignInForm';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function LoginPage() {
  const { user, initialized } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (initialized && user) {
      router.replace('/dashboard');
    }
  }, [user, initialized, router]);

  // Se ainda está carregando ou usuário está autenticado, não mostra nada
  if (!initialized || user) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
      <Card className="w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Entrar</h1>
          <p className="text-gray-600 mt-2">Faça login na sua conta</p>
        </div>
        
        <SignInForm />
        
        <div className="mt-4 text-center">
          <p className="text-sm text-gray-600">
            Não tem uma conta? {' '}
            <Link 
              href="/auth/sign-up" 
              className="text-blue-600 hover:underline"
            >
              Cadastre-se
            </Link>
          </p>
        </div>
      </Card>
    </div>
  );
}