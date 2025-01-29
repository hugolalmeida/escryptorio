// services/log-service.ts
import { prisma } from "@/lib/prisma"
import { DocumentType, DocumentStatus } from "@prisma/client"

export async function createLog(
  userId: string,
  documentType: DocumentType,
  fileName: string
) {
  return prisma.generationLog.create({
    data: {
      userId,
      documentType,
      fileName,
      status: "PENDING"
    }
  })
}

export async function updateLogStatus(
  id: string,
  status: DocumentStatus,
  error?: string
) {
  return prisma.generationLog.update({
    where: { id },
    data: { status, error }
  })
}