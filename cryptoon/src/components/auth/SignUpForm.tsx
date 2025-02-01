// src/components/auth/SignUpForm.tsx
'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';
import { z } from 'zod';
import router from 'next/router';

const signUpSchema = z.object({
  email: z.string().email('E-mail inválido'),
  password: z.string()
    .min(8, 'Senha deve ter no mínimo 8 caracteres')
    .regex(/[A-Z]/, 'Senha deve conter pelo menos uma letra maiúscula')
    .regex(/[a-z]/, 'Senha deve conter pelo menos uma letra minúscula')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um número')
    .regex(/[!@#$%^&*]/, 'Senha deve conter pelo menos um caractere especial'),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Senhas não coincidem',
  path: ['confirmPassword']
});

export const SignUpForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{ 
    email?: string; 
    password?: string; 
    confirmPassword?: string 
  }>({});
  const { signUp, loading, error: authError } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      // Valida os dados usando zod
      const validatedData = signUpSchema.parse({ 
        email, 
        password, 
        confirmPassword 
      });
      
      // Limpa erros anteriores
      setErrors({});
      
      // Chama método de cadastro
      const result = await signUp(validatedData.email, validatedData.password);

      console.log(validatedData.email);
      
      // Salva o email para usar na verificação
      window.localStorage.setItem("verifyEmail", validatedData.email);

      if (result.error) throw result.error;

      // // Redireciona para página de verificação
      // router.push('/auth/verify-email');

    } catch (err) {
      if (err instanceof z.ZodError) {
        // Trata erros de validação
        const fieldErrors = err.flatten().fieldErrors;
        setErrors({
          email: fieldErrors.email?.[0],
          password: fieldErrors.password?.[0],
          confirmPassword: fieldErrors.confirmPassword?.[0]
        });
      }
    }
  };

  return (
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
      <div>
        <Input 
          type="password"
          placeholder="Confirmar Senha"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={errors.confirmPassword}
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
        {loading ? 'Cadastrando...' : 'Cadastrar'}
      </Button>
    </form>
  );
};