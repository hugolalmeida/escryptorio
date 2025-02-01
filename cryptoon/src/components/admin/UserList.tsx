import { useAuth } from '@/contexts/AuthContext';

function AdminDashboard() {
    const { isAllowed } = useAuth();
  
    if (!isAllowed(['ADMIN'])) {
      return <AccessDenied />;
    }
  
    return (
      <div>
        <h1>Painel Administrativo</h1>
        {/* Conteúdo exclusivo para admin */}
      </div>
    );
  }