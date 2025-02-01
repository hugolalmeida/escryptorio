// src/types/auth.ts

import { createClientComponentClient } from "@supabase/auth-helpers-nextjs";
import { User } from "@supabase/supabase-js";

export type Role = 'BASIC' | 'PREMIUM' | 'ADMIN';

export interface UserProfile {
  id: string;
  role: Role;
  updated_at: string;
}

export interface AuthUser {
  id: string;
  email: string;
  profile?: UserProfile;
}

export interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: Error | null;
}

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  initialized: boolean;
  error: Error | null;
  signIn: (email: string, password: string) => Promise<any>;
  signUp: (email: string, password: string) => Promise<any>;
  signOut: () => Promise<void>;
  supabase: ReturnType<typeof createClientComponentClient>;
  isAllowed: (allowedRoles: Role[]) => boolean;
}