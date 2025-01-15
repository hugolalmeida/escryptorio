import { NextResponse } from "next/server";
import puppeteer from 'puppeteer';

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
    anotacoesGerais,
    cryptoAssets,
  } = await request.json();

  // Cria o conteúdo HTML
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 20px;
            }
            .header {
                text-align: center;
                margin-bottom: 20px;
            }
            .section {
                margin-bottom: 20px;
            }
            .section-title {
                background-color: #f0f0f0;
                padding: 5px;
                margin-bottom: 10px;
            }
            .crypto-item {
                margin-bottom: 15px;
                padding-left: 20px;
            }
            .field {
                margin-bottom: 5px;
            }
            @page {
                margin: 20px;
            }
            
            .notes-content {
  white-space: pre-wrap;
  padding: 10px;
  background-color: #f9f9f9;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin: 10px 0;
}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Ficha de Levantamento de Criptoativos</h1>
        </div>

        <div class="section">
            <h2 class="section-title">Dados do Proprietário</h2>
            <div class="field">Nome Completo: ${nomeCompleto || "_________________________"}</div>
            <div class="field">CPF/CNPJ: ${cpfCnpj || "_________________________"}</div>
            <div class="field">Endereço: ${rua || "__________"}, ${numero || "___"}</div>
            ${complemento ? `<div class="field">Complemento: ${complemento}</div>` : ''}
            <div class="field">Bairro: ${bairro || "__________"}</div>
            <div class="field">Cidade: ${cidade || "__________"} - ${estado || "__"}</div>
            <div class="field">CEP: ${cep || "__________"}</div>
            <div class="field">Telefone: ${telefone || "__________"}</div>
            <div class="field">E-mail: ${email || "__________"}</div>
        </div>

        <div class="section">
            <h2 class="section-title">Informações dos Criptoativos</h2>
            ${cryptoAssets.map((asset: any, index: number) => `
                <div class="crypto-item">
                    <h3>${index + 1}. Criptoativo</h3>
                    <div class="field">Nome da Moeda: ${asset.coinName || "_________________________"}</div>
                    <div class="field">Quantidade: ${asset.quantity || "_________________________"}</div>
                    <div class="field">Endereço da Wallet: ${asset.walletAddress || "_________________________"}</div>
                    <div class="field">Exchange/Plataforma: ${asset.exchange || "_________________________"}</div>
                </div>
            `).join('')}
        </div>

        ${anotacoesGerais ? `
          <div class="section">
            <h2 class="section-title">Anotações Gerais</h2>
            <div class="notes-content">
              ${anotacoesGerais.split('\n').map((line: any) => `<p>${line}</p>`).join('')}
            </div>
          </div>
        ` : `
          <div class="section">
            <h2 class="section-title">Anotações Gerais</h2>
            <div style="border-bottom: 1px solid #000; margin: 10px 0;">_____________________________________________</div>
            <div style="border-bottom: 1px solid #000; margin: 10px 0;">_____________________________________________</div>
            <div style="border-bottom: 1px solid #000; margin: 10px 0;">_____________________________________________</div>
          </div>
        `}

        <div class="signature-section">
            <h2>Assinatura do Proprietário</h2>
            <div style="display: flex; gap: 20px; margin-bottom: 10px;">
                <div>Local: _________________</div>
                <div>Data: ____/____/____</div>
            </div>
            <div style="border-top: 1px solid #000; width: 200px; margin-top: 50px;"></div>
            <div style="text-align: center;">Assinatura do Proprietário</div>
        </div>
    </body>
    </html>
  `;

  try {
    // Iniciar o navegador
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();

    // Configurar o conteúdo HTML
    await page.setContent(htmlContent, { waitUntil: 'networkidle0' });

    // Gerar PDF
    const pdf = await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: {
        top: '20px',
        right: '20px',
        bottom: '20px',
        left: '20px'
      }
    });

    // Fechar o navegador
    await browser.close();

    return new NextResponse(pdf, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": "attachment; filename=Ficha_de_Levantamento.pdf",
      },
    });
  } catch (error) {
    console.error(error);
    return new NextResponse('Erro ao gerar PDF', { status: 500 });
  }
}