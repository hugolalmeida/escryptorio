// app/dashboard/page.tsx

import SupabaseTest from '@/components/dev/SupabaseTest';

export default function Dashboard() {
  return (
    <div>
      {/* Conteúdo existente do dashboard */}
      
      {process.env.NODE_ENV === 'development' && (
        <SupabaseTest />
      )}
    </div>
  );
}