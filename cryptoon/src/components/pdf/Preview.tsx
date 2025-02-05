// components/pdf/Preview.tsx
'use client';

import React from 'react';
import { PDFViewer } from '@react-pdf/renderer';
import ContractTemplate from './templates/ContractTemplate';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

const PDFPreview = ({ data, onDownload, onClose }) => {
  return (
    <Card className="w-full max-w-4xl mx-auto p-4">
      <div className="flex justify-end space-x-4 mb-4">
        <Button variant="outline" onClick={onClose}>
          Fechar
        </Button>
        <Button onClick={onDownload}>
          Download PDF
        </Button>
      </div>
      
      <PDFViewer className="w-full h-[calc(100vh-200px)]">
        <ContractTemplate data={data} />
      </PDFViewer>
    </Card>
  );
};

export default PDFPreview;