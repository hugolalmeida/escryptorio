'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import ContractForm from '@/components/forms/ContractForm';

// Importar PDFPreview dinamicamente para evitar problemas de SSR
const PDFPreview = dynamic(() => import('@/components/pdf/Preview'), {
  ssr: false,
});

const ContractPage = () => {
  const [showPreview, setShowPreview] = useState(false);
  const [formData, setFormData] = useState(null);

  const handleSubmit = (data) => {
    setFormData(data);
    setShowPreview(true);
  };

  const handleDownload = async () => {
    if (formData) {
      const PDFDownload = (await import('@/components/pdf/Download')).default;
      PDFDownload(formData);
    }
  };

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-3xl font-bold mb-6">Ficha de Levantamento de Criptoativos</h1>
      
      {showPreview ? (
        <PDFPreview
          data={formData}
          onDownload={handleDownload}
          onClose={() => setShowPreview(false)}
        />
      ) : (
        <ContractForm onSubmit={handleSubmit} />
      )}
    </div>
  );
};

export default ContractPage;