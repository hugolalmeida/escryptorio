// components/dev/SupabaseTest.tsx
'use client';

import { useSupabaseTest } from '@/hooks/useSupabaseTest';

export default function SupabaseTest() {
  const { testConnection, isLoading, error, result } = useSupabaseTest();

  return (
    <div className="p-4 border rounded-lg bg-gray-50">
      <h2 className="text-lg font-semibold mb-4">Teste de Conexão Supabase</h2>
      
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <button
            onClick={testConnection}
            disabled={isLoading}
            className={`px-4 py-2 rounded ${
              isLoading 
                ? 'bg-gray-400' 
                : 'bg-blue-500 hover:bg-blue-600'
            } text-white`}
          >
            {isLoading ? 'Testando...' : 'Testar Conexão'}
          </button>
          
          {isLoading && (
            <span className="text-gray-500">Verificando conexão...</span>
          )}
        </div>

        {error && (
          <div className="p-3 bg-red-100 border border-red-300 rounded text-red-700">
            Erro: {error}
          </div>
        )}

        {result && (
          <div className="p-3 bg-green-100 border border-green-300 rounded text-green-700">
            {result}
          </div>
        )}
      </div>

      <div className="mt-4 text-sm text-gray-600">
        <p>Verifique também o console do navegador para logs detalhados.</p>
      </div>
    </div>
  );
}