// services/pdf.service.ts

import { logService } from './supabase/logs';
import type { GenerationLog } from '@/types/supabase';

export const pdfService = {
  async generateDocument(
    userId: string,
    documentType: GenerationLog['document_type'],
    fileName: string,
    metadata: Record<string, any>
  ) {
    // Criar log inicial
    const { data: log } = await logService.createLog({
        user_id: userId,
        document_type: documentType,
        file_name: fileName,
        status: 'PENDING',
        metadata,
        error: null
    });

    try {
      // Lógica de geração do PDF aqui
      // ...

      // Atualizar log após sucesso
      if (log) {
        await logService.updateLogStatus(log.id, 'COMPLETED');
      }

      return { success: true, error: null };
    } catch (error) {
      // Atualizar log em caso de erro
      if (log) {
        await logService.updateLogStatus(
          log.id,
          'FAILED',
          error instanceof Error ? error.message : 'Unknown error'
        );
      }

      return { success: false, error };
    }
  }
};