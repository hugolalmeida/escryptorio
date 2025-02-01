// src/components/auth/ResetPasswordForm.tsx
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input'
import { useAuth } from "@/contexts/AuthContext"

const resetPasswordSchema = z.object({
  email: z.string().email("Email inválido"),
})

type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>

export function ResetPasswordForm() {
  const { supabase } = useAuth()
  
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  })

  const onSubmit = async (data: ResetPasswordFormData) => {
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(data.email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/update-password`,
      })

      if (error) throw error

      // Mostrar mensagem de sucesso
      alert("Verifique seu email para redefinir sua senha")
    } catch (error) {
      console.error("Erro ao enviar email de recuperação:", error)
      setError("email", {
        type: "manual",
        message: "Erro ao enviar email de recuperação",
      })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <Input
          label="Email"
          type="email"
          error={errors.email?.message}
          {...register("email")}
        />
      </div>
      <Button
        type="submit"
        className="w-full"
        disabled={isSubmitting}
      >
        {isSubmitting ? "Enviando..." : "Enviar email de recuperação"}
      </Button>
    </form>
  )
}