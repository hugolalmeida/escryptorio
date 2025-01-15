import { NextResponse } from "next/server";
import { jsPDF } from "jspdf";

export async function POST(request: Request) {
  const {
    nomeCompleto,
    cpfCnpj,
    rua,
    numero,
    complemento,
    bairro,
    cidade,
    estado,
    cep,
    telefone,
    email,
    cryptoAssets, // Array de criptoativos [{ id, coinName, quantity, walletAddress, exchange }]
  } = await request.json();

  const doc = new jsPDF();
  const pageHeight = 297; // Altura da página A4 em mm
  let y = 10; // Posição inicial vertical

  // Função para verificar limite da página e criar nova página, se necessário
  const checkPageLimit = () => {
    if (y >= pageHeight - 20) {
      doc.addPage();
      y = 10; // Reseta a posição vertical para o topo da nova página
    }
  };

  // Título
  doc.setFontSize(16);
  doc.text("Ficha de Levantamento de Criptoativos", 105, y, { align: "center" });
  y += 10;

  // Divisor
  doc.setLineWidth(0.5);
  doc.line(10, y, 200, y);
  y += 5;

  // Seção: Dados do Proprietário
  doc.setFontSize(12);
  doc.text("Dados do Proprietário", 10, y);
  y += 5;
  doc.line(10, y, 200, y);
  y += 5;

  const userInfo = [
    `Nome Completo: ${nomeCompleto || "_________________________"}`,
    `CPF/CNPJ: ${cpfCnpj || "_________________________"}`,
    `Endereço: ${rua || "__________"}, ${numero || "___"}`,
    complemento ? `Complemento: ${complemento}` : null,
    `Bairro: ${bairro || "__________"}`,
    `Cidade: ${cidade || "__________"} - ${estado || "__"}`,
    `CEP: ${cep || "__________"}`,
    `Telefone: ${telefone || "__________"}`,
    `E-mail: ${email || "__________"}`,
  ].filter(Boolean);

  userInfo.forEach((info) => {
    doc.text(info, 10, y);
    y += 10;
    checkPageLimit();
  });

  // Seção: Informações dos Criptoativos
  doc.setFontSize(12);
  doc.text("Informações dos Criptoativos", 10, y);
  y += 5;
  doc.line(10, y, 200, y);
  y += 5;

  cryptoAssets.forEach((asset: { coinName: any; quantity: any; walletAddress: any; exchange: any; }, index: number) => {
    const assetInfo = [
      `${index + 1}. Criptoativo`,
      `  Nome da Moeda: ${asset.coinName || "_________________________"}`,
      `  Quantidade: ${asset.quantity || "_________________________"}`,
      `  Endereço da Wallet: ${asset.walletAddress || "_________________________"}`,
      `  Exchange/Plataforma de Armazenamento: ${asset.exchange || "_________________________"}`,
    ];

    assetInfo.forEach((info) => {
      doc.text(info, 10, y);
      y += 10;
      checkPageLimit();
    });
    y += 5; // Espaçamento entre criptoativos
    checkPageLimit();
  });

  // Anotações Gerais
  doc.text("Anotações Gerais:", 10, y);
  y += 10;
  doc.text("__________________________________________________________", 10, y);
  y += 10;
  doc.text("__________________________________________________________", 10, y);
  y += 10;
  doc.text("__________________________________________________________", 10, y);
  y += 10;
  checkPageLimit();

  // Assinatura do Proprietário
  doc.text("Assinatura do Proprietário", 10, y);
  y += 10;
  doc.text("Local: ______________________", 10, y);
  doc.text("Data: ____/____/____", 100, y);
  y += 10;
  doc.text("Assinatura: __________________________________", 10, y);

  // Gera o PDF
  const pdf = doc.output("blob");

  return new NextResponse(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": "attachment; filename=Ficha_de_Levantamento.pdf",
    },
  });
}
