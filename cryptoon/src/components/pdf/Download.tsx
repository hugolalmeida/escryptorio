import React from 'react';
import { pdf } from '@react-pdf/renderer';
import ContractTemplate from './templates/ContractTemplate';

interface PDFDownloadProps {
  data: any;
  fileName?: string;
}

const PDFDownload = async ({ data, fileName }: PDFDownloadProps) => {
  try {
    // Gerar o PDF usando react-pdf
    const blob = await pdf(<ContractTemplate data={data} />).toBlob();
    
    // Criar URL do blob
    const url = URL.createObjectURL(blob);
    
    // Criar elemento de download
    const link = document.createElement('a');
    link.href = url;
    
    // Permitir que o usuário escolha o nome do arquivo
    // Se nenhum nome for fornecido, usa o padrão com timestamp
    const defaultName = `crypto-document-${Date.now()}.pdf`;
    link.download = fileName || defaultName;
    
    // Adicionar ao documento e simular clique
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Erro ao gerar PDF:', error);
    throw new Error('Falha ao gerar o PDF');
  }
};

export default PDFDownload;