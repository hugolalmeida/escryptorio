// services/supabase/logs.ts

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import type { GenerationLog, DBResult } from '@/types/supabase';

const supabase = createClientComponentClient();

export const logService = {
  async createLog(log: Omit<GenerationLog, 'id' | 'generated_at'>): Promise<DBResult<GenerationLog>> {
    try {
      const { data, error } = await supabase
        .from('generation_logs')
        .insert([log])
        .select()
        .single();

      return { data, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to create log', code: '500' } };
    }
  },

  async getUserLogs(userId: string): Promise<DBResult<GenerationLog[]>> {
    try {
      const { data, error } = await supabase
        .from('generation_logs')
        .select('*')
        .eq('user_id', userId)
        .order('generated_at', { ascending: false });

      return { data, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to fetch logs', code: '500' } };
    }
  },

  async updateLogStatus(
    logId: string,
    status: GenerationLog['status'],
    error?: string
  ): Promise<DBResult<GenerationLog>> {
    try {
      const { data, error: dbError } = await supabase
        .from('generation_logs')
        .update({
          status,
          error: error || null,
        })
        .eq('id', logId)
        .select()
        .single();

      return { data, error: dbError };
    } catch (error) {
      return { data: null, error: { message: 'Failed to update log status', code: '500' } };
    }
  },

  async getLogsByDocumentType(
    userId: string,
    documentType: GenerationLog['document_type']
  ): Promise<DBResult<GenerationLog[]>> {
    try {
      const { data, error } = await supabase
        .from('generation_logs')
        .select('*')
        .eq('user_id', userId)
        .eq('document_type', documentType)
        .order('generated_at', { ascending: false });

      return { data, error };
    } catch (error) {
      return { data: null, error: { message: 'Failed to fetch logs by document type', code: '500' } };
    }
  }
};