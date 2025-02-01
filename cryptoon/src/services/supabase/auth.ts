// src/services/supabase/auth.ts

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import { Role, UserProfile } from '@/types/auth';

export class AuthService {
  private supabase = createClientComponentClient();

  async signUp(email: string, password: string) {
    const { data, error } = await this.supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) throw error;

    // Create profile with default role
    if (data.user) {
      await this.supabase
        .from('profiles')
        .insert([{ id: data.user.id, role: 'BASIC' as Role }]);
    }

    return data;
  }

  async signIn(email: string, password: string) {
    const { data, error } = await this.supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) throw error;
    return data;
  }

  async signOut() {
    const { error } = await this.supabase.auth.signOut();
    if (error) throw error;
  }

  async getProfile(userId: string): Promise<UserProfile | null> {
    const { data, error } = await this.supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .single();

    if (error) throw error;
    return data;
  }

  async updateRole(userId: string, role: Role) {
    const { error } = await this.supabase
      .from('profiles')
      .update({ role, updated_at: new Date().toISOString() })
      .eq('id', userId);

    if (error) throw error;
  }

  // src/services/supabase/auth.ts
  // Adicione esta função ao arquivo existente
  async sendVerificationEmail (email: string) {
    const { data, error } = await this.supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    })

    if (error) throw error
    
    // Salva o email para usar na verificação
    window.localStorage.setItem("verifyEmail", email)
    
    return data
  }

}

export const authService = new AuthService();