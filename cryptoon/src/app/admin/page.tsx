// src/app/dashboard/admin/page.tsx
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

export default function AdminDashboardPage() {
  return (
    <ProtectedRoute allowedRoles={['ADMIN']} children={undefined}>
      {/* Conteúdo do dashboard admin */}
    </ProtectedRoute>
  );
}