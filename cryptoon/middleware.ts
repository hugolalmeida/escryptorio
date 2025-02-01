// middleware.ts
import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Rotas públicas que não requerem autenticação
const publicRoutes = [
  '/login', 
  '/auth/sign-up', 
  '/auth/callback',
  '/public'  // Adicione rotas públicas aqui
];

// Mapeamento de rotas para roles necessárias
const routeRoles = {
  '/dashboard/admin': ['ADMIN'],
  '/dashboard/premium': ['PREMIUM', 'ADMIN'],
};

export async function middleware(req: NextRequest) {
  const res = NextResponse.next();
  const supabase = createMiddlewareClient({ req, res });

  const {
    data: { session },
  } = await supabase.auth.getSession();

  const path = req.nextUrl.pathname;

  // Rotas públicas
  if (publicRoutes.some(route => path.startsWith(route))) {
    if (session) {
      return NextResponse.redirect(new URL('/dashboard', req.url));
    }
    return res;
  }

  // Verificação de autenticação para rotas protegidas
  if (!session) {
    return NextResponse.redirect(new URL('/login', req.url));
  }

  // Verificação de roles para rotas específicas
  for (const [route, allowedRoles] of Object.entries(routeRoles)) {
    if (path.startsWith(route)) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('role')
        .eq('id', session.user.id)
        .single();

      if (!allowedRoles.includes(profile?.role)) {
        return NextResponse.redirect(new URL('/dashboard', req.url));
      }
    }
  }

  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};