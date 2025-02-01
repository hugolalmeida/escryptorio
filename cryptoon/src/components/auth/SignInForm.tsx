// src/components/auth/SignInForm.tsx
'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';
import { z } from 'zod';
import Link from 'next/link';

const signInSchema = z.object({
  email: z.string().email('E-mail inválido'),
  password: z.string().min(6, 'Senha deve ter no mínimo 6 caracteres')
});

export const SignInForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const { signIn, loading, error: authError } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      // Valida os dados usando zod
      const validatedData = signInSchema.parse({ email, password });
      
      // Limpa erros anteriores
      setErrors({});
      
      // Chama método de login
      await signIn(validatedData.email, validatedData.password);
    } catch (err) {
      if (err instanceof z.ZodError) {
        // Trata erros de validação
        const fieldErrors = err.flatten().fieldErrors;
        setErrors({
          email: fieldErrors.email?.[0],
          password: fieldErrors.password?.[0]
        });
      }
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Input 
            type="email"
            placeholder="E-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
          />
        </div>
        <div>
          <Input 
            type="password"
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
          />
        </div>
        {authError && (
          <div className="text-red-500 text-sm">
            {authError.message}
          </div>
        )}
        <Button 
          type="submit" 
          disabled={loading}
          className="w-full"
        >
          {loading ? 'Entrando...' : 'Entrar'}
        </Button>
      </form>
      
      <div className="text-center space-y-2">
        <Link 
          href="/auth/reset-password" 
          className="text-sm text-blue-600 hover:text-blue-800 block"
        >
          Esqueceu sua senha?
        </Link>
      </div>
    </div>
  );
};