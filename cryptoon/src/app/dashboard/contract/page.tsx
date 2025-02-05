'use client';
import React, { useState } from 'react';
import ContractForm from '@/components/forms/ContractForm';
import { pdf } from '@react-pdf/renderer';
import CryptoDocument from '@/components/pdf/templates/ContractTemplate';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from '@/hooks/use-toast';

const ContractPage = () => {
  const [formKey, setFormKey] = useState(0);
  const [showDialog, setShowDialog] = useState(false);

  const handleSubmit = async (data: any) => {
    try {
      // Gerar o PDF
      const blob = await pdf(<CryptoDocument data={data} />).toBlob();
      const url = URL.createObjectURL(blob);
      
      // Abrir em nova aba
      window.open(url, '_blank');
      
      // Cleanup após um breve delay
      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);

      // Mostrar toast de sucesso
      toast({
        title: "PDF Gerado com Sucesso",
        description: "O documento foi aberto em uma nova aba.",
      });
      
      // Mostrar diálogo após um breve delay
      setTimeout(() => {
        setShowDialog(true);
      }, 1000);

    } catch (error) {
      console.error('Erro ao gerar PDF:', error);
      toast({
        title: "Erro ao gerar PDF",
        description: "Houve um erro ao gerar o documento. Por favor, tente novamente.",
        variant: "destructive",
      });
    }
  };

  const handleNewDocument = () => {
    setShowDialog(false);
    setFormKey(prev => prev + 1); // Força o reset do formulário
    toast({
      title: "Formulário Resetado",
      description: "Você pode começar a preencher um novo documento.",
    });
  };

  const handleKeepCurrent = () => {
    setShowDialog(false);
  };

  return (
    <div className="container mx-auto py-6">
      <ContractForm key={formKey} onSubmit={handleSubmit} />

      <AlertDialog open={showDialog} onOpenChange={setShowDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Gerar novo documento?</AlertDialogTitle>
            <AlertDialogDescription>
              O PDF foi gerado com sucesso. Deseja criar um novo documento ou manter os dados atuais?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleKeepCurrent}>
              Manter Dados
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleNewDocument}>
              Novo Documento
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ContractPage;