import { NextResponse } from "next/server";
import { jsPDF } from "jspdf";

export async function POST(request: Request) {
  const { nome, email, mensagem } = await request.json();

  const doc = new jsPDF();
  doc.text(`Nome: ${nome}`, 10, 10);
  doc.text(`Email: ${email}`, 10, 20);
  doc.text(`Mensagem: ${mensagem}`, 10, 30);

  const pdf = doc.output("blob");
  return new NextResponse(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": "attachment; filename=documento.pdf",
    },
  });
}
