'use client'
// src/contexts/AuthContext.tsx

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import { AuthContextType, AuthState, Role } from '@/types/auth';
import { authService } from '@/services/supabase/auth';
import { User } from '@supabase/auth-helpers-nextjs';

const initialState: AuthState = {
  user: null,
  loading: true,
  error: null,
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [state, setState] = useState<AuthState>(initialState);
  const router = useRouter();
  const supabase = createClientComponentClient();

  useEffect(() => {
    const initialize = async () => {
      try {
        // Verifica a sessão atual
        const { data: { session } } = await supabase.auth.getSession();
        setUser(session?.user ?? null);
        
        // Configura listener para mudanças de auth
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
          async (event, session) => {
            setUser(session?.user ?? null);
            setLoading(false);
          }
        );

        return () => {
          subscription.unsubscribe();
        };
      } catch (error) {
        console.error('Erro ao inicializar auth:', error);
      } finally {
        setInitialized(true);
        setLoading(false);
      }
    };

    initialize();
  }, [supabase]);

  const signIn = async (email: string, password: string) => {
    try {
      setLoading(true);
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      return { data, error: null };
    } catch (error) {
      return { data: null, error };
    } finally {
      setLoading(false);
    }
  };

  const signUp = async (email: string, password: string) => {
    try {
      await authService.signUp(email, password);
      // Usually would show a "verify email" message
      router.push('/auth/verify-email');
    } catch (error) {
      setState(prev => ({ ...prev, error: error as Error }));
    }
  };

  const signOut = async () => {
    setLoading(true);
    try {
      await supabase.auth.signOut();
    } catch (error) {
      console.error('Erro ao fazer logout:', error);
    } finally {
      setLoading(false);
    }
  };

  const isAllowed = (allowedRoles: Role[]) => {
    return state.user?.profile && allowedRoles.includes(state.user.profile.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        initialized,
        error,
        signIn,
        signUp,
        signOut,
        supabase,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};