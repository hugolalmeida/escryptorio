import { NextResponse } from "next/server";
import { jsPDF } from "jspdf";
import 'jspdf-autotable';

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
    cryptoAssets,
    anotacoesGerais,
  } = await request.json();

  // Criar novo documento PDF
  const doc = new jsPDF();
  
  // Configurações iniciais
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 20;
  let y = margin;

  // Cores
  const primaryColor = [0, 0.4, 0.8]; // Azul
  const secondaryColor = [0.2, 0.2, 0.2]; // Cinza escuro
  const borderColor = [0.8, 0.8, 0.8]; // Cinza claro

  // Função para adicionar cabeçalho em cada página
  const addHeader = () => {
    doc.setFillColor(245, 245, 245); // Fundo cinza claro
    doc.rect(0, 0, pageWidth, 30, 'F');
    
    // Espaço para logo (50x20mm)
    doc.rect(margin, 5, 50, 20);
    doc.setFontSize(8);
    doc.text("Logo aqui", margin + 25, 15, { align: "center" });

    // Título do documento ao lado da logo
    doc.setFontSize(16);
    doc.setTextColor(...primaryColor);
    doc.text("Ficha de Levantamento de Criptoativos", margin + 60, 15);
    
    // Linha divisória
    doc.setDrawColor(...borderColor);
    doc.line(0, 30, pageWidth, 30);

    return 40; // Retorna a posição Y após o cabeçalho
  };

  // Função para adicionar seção com borda
  const addSection = (title: string, yPos: number) => {
    doc.setDrawColor(...borderColor);
    doc.setFillColor(250, 250, 250);
    
    // Título da seção
    doc.setFontSize(14);
    doc.setTextColor(...primaryColor);
    doc.text(title, margin, yPos);
    
    // Linha abaixo do título
    doc.line(margin, yPos + 2, pageWidth - margin, yPos + 2);
    
    return yPos + 2;
  };

  // Função para verificar espaço na página
  const checkSpace = (neededSpace: number) => {
    if (y + neededSpace > pageHeight - margin) {
      doc.addPage();
      y = addHeader();
    }
  };

  // Adicionar cabeçalho na primeira página
  y = addHeader();

  // Seção: Dados do Proprietário
  y = addSection("Dados do Proprietário", y);
  y += 5;

  doc.setFontSize(12);
  doc.setTextColor(...secondaryColor);
  
  // Criar tabela para dados pessoais
  const dadosPessoais = [
    [{ content: 'Nome Completo:', colSpan: 1 }, { content: nomeCompleto || "", colSpan: 3 }],
    [{ content: 'CPF/CNPJ:', colSpan: 1 }, { content: cpfCnpj || "", colSpan: 3 }],
    [{ content: 'Endereço:', colSpan: 1 }, { content: `${rua || ""}, ${numero || ""}`, colSpan: 3 }],
    complemento ? [{ content: 'Complemento:', colSpan: 1 }, { content: complemento, colSpan: 3 }] : null,
    [
      { content: 'Bairro:', colSpan: 1 }, { content: bairro || "", colSpan: 1 },
      { content: 'CEP:', colSpan: 1 }, { content: cep || "", colSpan: 1 }
    ],
    [
      { content: 'Cidade:', colSpan: 1 }, { content: cidade || "", colSpan: 1 },
      { content: 'Estado:', colSpan: 1 }, { content: estado || "", colSpan: 1 }
    ],
    [
      { content: 'Telefone:', colSpan: 1 }, { content: telefone || "", colSpan: 1 },
      { content: 'E-mail:', colSpan: 1 }, { content: email || "", colSpan: 1 }
    ],
  ].filter(Boolean);

  doc.autoTable({
    startY: y,
    body: dadosPessoais,
    theme: 'grid',
    styles: {
      fontSize: 10,
      cellPadding: 5,
    },
    columnStyles: {
      0: { fontStyle: 'bold', width: 30 },
      2: { fontStyle: 'bold' },
    },
    margin: { left: margin, right: margin },
  });

  y = (doc as any).lastAutoTable.finalY + 10;

  // Seção: Informações dos Criptoativos
  checkSpace(40);
  y = addSection("Informações dos Criptoativos", y);
  y += 5;

  // Tabela de criptoativos
  const cryptoHeaders = [
    'Nº',
    'Nome da Moeda',
    'Quantidade',
    'Endereço da Wallet',
    'Exchange/Plataforma'
  ];

  const cryptoData = cryptoAssets.map((asset: any, index: number) => [
    index + 1,
    asset.coinName || "",
    asset.quantity || "",
    asset.walletAddress || "",
    asset.exchange || ""
  ]);

  doc.autoTable({
    startY: y,
    head: [cryptoHeaders],
    body: cryptoData,
    theme: 'grid',
    styles: {
      fontSize: 10,
      cellPadding: 5,
    },
    headStyles: {
      fillColor: [245, 245, 245],
      textColor: [1, 1, 1],
      fontStyle: 'bold',
    },
    margin: { left: margin, right: margin },
  });

  y = (doc as any).lastAutoTable.finalY + 10;

  // Seção: Anotações Gerais
  checkSpace(40);
  y = addSection("Anotações Gerais", y);
  y += 5;

  if (anotacoesGerais && anotacoesGerais.trim()) {
    doc.autoTable({
      startY: y,
      body: [[anotacoesGerais]],
      theme: 'plain',
      styles: {
        fontSize: 10,
        cellPadding: 5,
      },
      margin: { left: margin, right: margin },
    });
    y = (doc as any).lastAutoTable.finalY + 5;
  } else {
    doc.autoTable({
      startY: y,
      body: [[''], [''], ['']],
      theme: 'plain',
      styles: {
        fontSize: 10,
        cellPadding: 10,
        lineWidth: 0.1,
      },
      margin: { left: margin, right: margin },
    });
    y = (doc as any).lastAutoTable.finalY + 10;
  }

  // Seção: Assinatura
  checkSpace(50);
  y += 10;
  
  // Local e Data
  doc.setFontSize(12);
  doc.setTextColor(...secondaryColor);
  
  doc.autoTable({
    startY: y,
    body: [
      [
        { content: 'Local: _______________________', styles: { halign: 'left' } },
        { content: 'Data: ____/____/____', styles: { halign: 'right' } }
      ],
      [{ content: '', colSpan: 2 }], // Espaço para assinatura
      [{ content: 'Assinatura do Proprietário', colSpan: 2, styles: { halign: 'center' } }]
    ],
    theme: 'plain',
    styles: {
      fontSize: 12,
      cellPadding: 5,
    },
    margin: { left: margin, right: margin },
  });

  // Gerar o PDF
  const pdf = doc.output("blob");

  return new NextResponse(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": "attachment; filename=Ficha_de_Levantamento.pdf",
    },
  });
}