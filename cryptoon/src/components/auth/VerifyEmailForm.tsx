// src/components/auth/VerifyEmailForm.tsx
'use client';

import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { useRouter } from "next/navigation"
import { Button } from "../shared/Button"
import { Input } from "../shared/Input"
import { useAuth } from "@/contexts/AuthContext" // Mudar para useAuth ao invés de useSupabaseAuth

const verifyEmailSchema = z.object({
  code: z.string().min(6, "Código inválido").max(6, "Código inválido"),
})

type VerifyEmailFormData = z.infer<typeof verifyEmailSchema>

export function VerifyEmailForm() {
  const router = useRouter()
  const { supabase } = useAuth() // Usando o contexto de autenticação
  
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError: setFormError,
  } = useForm<VerifyEmailFormData>({
    resolver: zodResolver(verifyEmailSchema),
  })

  const onSubmit = async (data: VerifyEmailFormData) => {
    try {
      const storedEmail = window.localStorage.getItem("verifyEmail")
      
      if (!storedEmail) {
        throw new Error("Email não encontrado. Por favor, tente se cadastrar novamente.")
      }

      const { error } = await supabase.auth.verifyOtp({
        email: storedEmail,
        token: data.code,
        type: 'signup'
      })

      if (error) throw error
      
      // Limpa o email do localStorage após verificação bem-sucedida
      window.localStorage.removeItem("verifyEmail")
      
      // Redireciona para o dashboard
      router.push("/dashboard")
    } catch (error) {
      console.error("Erro ao verificar email:", error)
      setFormError('code', {
        type: 'manual',
        message: error instanceof Error ? error.message : 'Erro ao verificar email'
      })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <Input
          label="Código de verificação"
          type="text"
          error={errors.code?.message}
          {...register("code")}
        />
      </div>
      <Button
        type="submit"
        className="w-full"
        disabled={isSubmitting}
      >
        {isSubmitting ? "Verificando..." : "Verificar email"}
      </Button>
    </form>
  )
}