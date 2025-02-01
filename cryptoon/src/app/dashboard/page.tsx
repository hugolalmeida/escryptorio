// app/dashboard/page.tsx

import SupabaseTest from '@/components/dev/SupabaseTest';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import {Header} from '@/components/layout/Header'

export default function Dashboard() {
  return (
    <div>
       <ProtectedRoute>
      {/* Conteúdo existente do dashboard */}
      <Header />
      {process.env.NODE_ENV === 'development' && (
        <SupabaseTest />
      )}
      </ProtectedRoute>
    </div>
  );
}