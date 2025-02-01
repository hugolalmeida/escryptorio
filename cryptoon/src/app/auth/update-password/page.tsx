'use client'

// src/app/auth/update-password/page.tsx
import { UpdatePasswordForm } from '@/components/auth/UpdatePasswordForm'
import { Card } from '@/components/shared/Card';


export default function UpdatePassword() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-8 px-4">
      <Card className="w-full max-w-md">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Atualizar Senha</h2>
          <p className="mt-2 text-gray-600">
            Digite sua nova senha
          </p>
        </div>
        <UpdatePasswordForm />
       </Card> 
      </div>
    </div>
  )
}