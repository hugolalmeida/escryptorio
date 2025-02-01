'use client'
// src/app/auth/verify-email/page.tsx
import { VerifyEmailForm } from "@/components/auth/VerifyEmailForm"
import { BackButton } from "@/components/shared/BackButton"
import { Card } from '@/components/shared/Card';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function VerifyEmail() {
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
      <Card className="w-full max-w-md">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Verifique seu email</h2>
          <p className="mt-2 text-gray-600">
            Digite o código que enviamos para seu email
          </p>
        </div>
        <VerifyEmailForm />
      </ Card>
      </div>
    </div>
  )
}

