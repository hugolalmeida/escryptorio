'use client'
// src/app/auth/reset-password/page.tsx
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm"
import { BackButton } from "@/components/shared/BackButton"
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ResetPassword() {
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
    <div className="relative flex min-h-screen items-center justify-center">
      <BackButton href="/login" />
      <div className="w-full max-w-md space-y-8 px-4">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Recuperar senha</h2>
          <p className="mt-2 text-gray-600">
            Digite seu email para receber as instruções
          </p>
        </div>
        <ResetPasswordForm />
      </div>
    </div>
  )
}

