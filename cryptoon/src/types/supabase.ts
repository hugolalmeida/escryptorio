// types/supabase.ts

export type Profile = {
    id: string;
    role: 'BASIC' | 'PREMIUM' | 'ADMIN';
    updated_at: string | null;
  };
  
  export type GenerationLog = {
    id: string;
    user_id: string;
    document_type: 'CONTRACT' | 'KEY';
    file_name: string;
    status: 'PENDING' | 'COMPLETED' | 'FAILED';
    generated_at: string;
    error: string | null;
    metadata: Record<string, any>;
  };
  
  // Tipos para respostas do Supabase
  export type DBError = {
    message: string;
    code: string;
  };
  
  export type DBResult<T> = {
    data: T | null;
    error: DBError | null;
  };