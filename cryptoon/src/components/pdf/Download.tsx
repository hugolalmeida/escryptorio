import React from 'react';
import { pdf } from '@react-pdf/renderer';
import CryptoDocument from './templates/ContractTemplate';

const PDFDownload = async (data) => {
  const blob = await pdf(<CryptoDocument data={data} />).toBlob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `crypto-document-${Date.now()}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

export default PDFDownload;