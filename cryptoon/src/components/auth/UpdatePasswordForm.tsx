// src/components/auth/UpdatePasswordForm.tsx
'use client';

import { useState } from 'react';
import { useAuth } from "@/contexts/AuthContext"
import { useRouter } from 'next/navigation';
import { Button } from '../shared/Button';
import { Input } from '../shared/Input';
import { z } from 'zod';

const updatePasswordSchema = z.object({
  password: z.string().min(6, 'A senha deve ter no mínimo 6 caracteres'),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: "As senhas não coincidem",
  path: ["confirmPassword"],
});

export function UpdatePasswordForm() {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { supabase } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // Valida os dados
      updatePasswordSchema.parse({ password, confirmPassword });

      // Atualiza a senha
      const { error: updateError } = await supabase.auth.updateUser({
        password: password
      });

      if (updateError) throw updateError;

      // Redireciona para o dashboard em caso de sucesso
      router.push('/dashboard');
    } catch (err) {
      if (err instanceof z.ZodError) {
        setError(err.errors[0].message);
      } else {
        setError('Erro ao atualizar senha. Tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <Input
          type="password"
          label="Nova senha"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div>
        <Input
          type="password"
          label="Confirme a nova senha"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />
      </div>
      {error && (
        <div className="text-red-500 text-sm">
          {error}
        </div>
      )}
      <Button
        type="submit"
        className="w-full"
        disabled={loading}
      >
        {loading ? 'Atualizando...' : 'Atualizar senha'}
      </Button>
    </form>
  );
}