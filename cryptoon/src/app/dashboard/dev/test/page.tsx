// app/dashboard/dev/test/page.tsx
import SupabaseTest from '@/components/dev/SupabaseTest';

export default function TestPage() {
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Página de Testes do Supabase</h1>
      <SupabaseTest />
    </div>
  );
}