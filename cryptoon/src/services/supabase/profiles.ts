// services/supabase/profiles.ts

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import type { Profile, DBResult } from '@/types/supabase';

const supabase = createClientComponentClient();

export const profileService = {
  async getProfile(userId: string): Promise<DBResult<Profile>> {
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

      return { data, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to fetch profile', code: '500' } };
    }
  },

  async updateProfile(userId: string, profile: Partial<Profile>): Promise<DBResult<Profile>> {
    try {
      const { data, error } = await supabase
        .from('profiles')
        .update({
          ...profile,
          updated_at: new Date().toISOString(),
        })
        .eq('id', userId)
        .select()
        .single();

      return { data, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to update profile', code: '500' } };
    }
  },

  async deleteProfile(userId: string): Promise<DBResult<null>> {
    try {
      const { error } = await supabase
        .from('profiles')
        .delete()
        .eq('id', userId);

      return { data: null, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to delete profile', code: '500' } };
    }
  }
};