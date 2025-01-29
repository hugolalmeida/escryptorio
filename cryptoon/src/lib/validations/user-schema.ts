// lib/validations/user.ts
import * as z from "zod"

export const userSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().optional(),
  role: z.enum(["BASIC", "PREMIUM", "ADMIN"])
})