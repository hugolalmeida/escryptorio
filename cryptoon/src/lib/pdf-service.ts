// lib/pdf-service.ts
import { ContractPDF } from '@/components/PDFDocument'
import { renderToFile } from '@react-pdf/renderer'

export async function generateContractPDF(contractData: any) {
  try {
    const filename = `contract-${contractData.id}.pdf`
    await renderToFile(
      <ContractPDF 
        title={contractData.title}
        content={contractData.content}
        key={contractData.cryptoKey}
      />,
      `./public/contracts/${filename}`
    )
    return filename
  } catch (error) {
    console.error('Error generating PDF:', error)
    throw error
  }
}