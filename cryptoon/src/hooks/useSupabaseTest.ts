// hooks/useSupabaseTest.ts
'use client';

import { useState } from 'react';
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';

const supabase = createClientComponentClient();

export const useSupabaseTest = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const testConnection = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    
    try {
      // Teste 1: Verificar conexão básica
      console.log('Testando conexão com Supabase...');
      const { data, error: pingError } = await supabase
        .from('profiles')
        .select('count')
        .limit(1);

      if (pingError) {
        throw new Error(`Conexão falhou: ${pingError.message}`);
      }

      console.log('Conexão bem sucedida!');
      setResult('Conexão com Supabase estabelecida com sucesso!');
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro desconhecido ao testar conexão';
      console.error('Erro no teste:', message);
      setError(message);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    testConnection,
    isLoading,
    error,
    result
  };
};