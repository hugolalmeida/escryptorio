// tests/integration/auth.test.ts
import { createClient } from '@supabase/supabase-js';
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { authService } from '@/services/supabase/auth';

// Configuração do Supabase para testes
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!, 
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

describe('Authentication Service', () => {
  const testUser = {
    email: `test-${Date.now()}@example.com`,
    password: 'TestPassword123!'
  };

  it('should successfully sign up a new user', async () => {
    const result = await authService.signUp(testUser.email, testUser.password);
    
    expect(result.user).toBeTruthy();
    expect(result.user?.email).toBe(testUser.email);
  });

  it('should sign in a registered user', async () => {
    // Primeiro, garante que o usuário está registrado
    await authService.signUp(testUser.email, testUser.password);
    
    const result = await authService.signIn(testUser.email, testUser.password);
    
    expect(result.user).toBeTruthy();
    expect(result.user?.email).toBe(testUser.email);
  });

  it('should fail to sign in with incorrect credentials', async () => {
    await expect(
      authService.signIn(testUser.email, 'wrongpassword')
    ).rejects.toBeTruthy();
  });

  // Limpa o usuário de teste após os testes
  afterAll(async () => {
    // Remove o usuário criado para testes
    const { data: { user } } = await supabase.auth.signInWithPassword({
      email: testUser.email,
      password: testUser.password
    });

    if (user) {
      await supabase.auth.admin.deleteUser(user.id);
    }
  });
});