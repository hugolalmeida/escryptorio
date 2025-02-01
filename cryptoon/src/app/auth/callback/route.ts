// src/app/auth/callback/route.ts
import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { type NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const next = requestUrl.searchParams.get('next') || '/dashboard'

  if (code) {
    const supabase = createRouteHandlerClient({ cookies })
    
    // Exchange the code for a session
    await supabase.auth.exchangeCodeForSession(code)

    // Redireciona baseado no parâmetro 'next' ou para o dashboard como padrão
    if (next === '/update-password') {
      return NextResponse.redirect(new URL('/auth/update-password', requestUrl.origin))
    }
    
    return NextResponse.redirect(new URL(next, requestUrl.origin))
  }

  // Se não houver código, redireciona para login
  return NextResponse.redirect(new URL('/login', requestUrl.origin))
}