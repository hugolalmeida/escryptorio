// lib/validations/log.ts
export const logSchema = z.object({
    documentType: z.enum(["CONTRACT", "KEY"]),
    fileName: z.string(),
    status: z.enum(["PENDING", "COMPLETED", "FAILED"]),
    metadata: z.record(z.any()).optional()
  })