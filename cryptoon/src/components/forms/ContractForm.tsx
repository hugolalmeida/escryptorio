'use client'

import React, { useState } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { PlusCircle, MinusCircle } from 'lucide-react';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { toast } from '@/hooks/use-toast';
// import { toast } from '@/components/ui/use-toast';

const formSchema = z.object({
  nome: z.string().min(3, 'Nome deve ter no mínimo 3 caracteres'),
  cpfCnpj: z.string()
    .min(11, 'CPF/CNPJ deve ter no mínimo 11 caracteres')
    .max(14, 'CPF/CNPJ deve ter no máximo 14 caracteres')
    .regex(/^\d+$/, 'CPF/CNPJ deve conter apenas números'),
  endereco: z.object({
    rua: z.string().min(1, 'Rua é obrigatória'),
    numero: z.string().min(1, 'Número é obrigatório'),
    complemento: z.string().optional(),
    bairro: z.string().min(1, 'Bairro é obrigatório'),
    cidade: z.string().min(1, 'Cidade é obrigatória'),
    estado: z.string().min(2, 'Estado é obrigatório').max(2, 'Use a sigla do estado'),
    cep: z.string()
      .min(8, 'CEP inválido')
      .max(8, 'CEP inválido')
      .regex(/^\d+$/, 'CEP deve conter apenas números'),
  }),
  telefone: z.string()
    .regex(/^\+55\d{2}9?\d{8}$/, 'Telefone deve estar no formato +55DDD999999999'),
  email: z.string().email('E-mail inválido'),
  criptoativos: z.array(z.object({
    nome: z.string().min(1, 'Nome da moeda é obrigatório'),
    quantidade: z.string().min(1, 'Quantidade é obrigatória'),
    wallet: z.string().min(1, 'Endereço da wallet é obrigatório'),
    exchange: z.string().min(1, 'Exchange é obrigatória'),
  })),
  anotacoes: z.string(),
  local: z.string().min(1, 'Local é obrigatório'),
  data: z.string().min(1, 'Data é obrigatória'),
  anotacoesGerais: z.string().optional(),
});

const ContractForm = ({ onSubmit }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 4; // Agora são 4 etapas

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      nome: '',
      cpfCnpj: '',
      endereco: {
        rua: '',
        numero: '',
        complemento: '',
        bairro: '',
        cidade: '',
        estado: '',
        cep: '',
      },
      telefone: '',
      email: '',
      criptoativos: [
        {
          nome: '',
          quantidade: '',
          wallet: '',
          exchange: '',
        },
      ],
      anotacoes: '',
      local: '',
      data: new Date().toISOString().split('T')[0],
      anotacoesGerais: '',
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "criptoativos"
  });

  const handleNextStep = async () => {
    const fields = {
      1: ['nome', 'cpfCnpj', 'telefone', 'email', 'endereco'],
      2: ['criptoativos'],
      3: ['anotacoesGerais'],
      4: ['local', 'data'],
    };

    const currentFields = fields[currentStep];
    
    const isValid = await form.trigger(currentFields);
    
    if (isValid) {
      setCurrentStep((prev) => Math.min(prev + 1, totalSteps));
    } else {
      toast({
        title: "Erro de validação",
        description: "Por favor, preencha todos os campos obrigatórios corretamente.",
        variant: "destructive",
      });
    }
  };

  const handlePrevStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const renderStep1 = () => (
    <Card className="p-6">
      <h2 className="text-2xl font-bold mb-4">Dados do Proprietário</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField
          control={form.control}
          name="nome"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nome Completo</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="cpfCnpj"
          render={({ field }) => (
            <FormItem>
              <FormLabel>CPF/CNPJ</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.rua"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Rua</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.numero"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Número</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.complemento"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Complemento</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.bairro"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Bairro</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.cidade"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Cidade</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.estado"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Estado</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="endereco.cep"
          render={({ field }) => (
            <FormItem>
              <FormLabel>CEP</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="telefone"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Telefone</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>E-mail</FormLabel>
              <FormControl>
                <Input {...field} type="email" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </Card>
  );

  const renderStep2 = () => (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold">Criptoativos</h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => append({
            nome: '',
            quantidade: '',
            wallet: '',
            exchange: '',
          })}
        >
          <PlusCircle className="w-4 h-4 mr-2" />
          Adicionar Criptoativo
        </Button>
      </div>

      {fields.map((field, index) => (
        <div key={field.id} className="mb-6 p-4 border rounded-lg">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">Criptoativo {index + 1}</h3>
            {index > 0 && (
              <>
              <div className="flex justify-between items-center mb-4">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => remove(index)}
              >
                <MinusCircle className="w-4 h-4 mr-2" />
                Remover
              </Button><Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => append({
                  nome: '',
                  quantidade: '',
                  wallet: '',
                  exchange: '',
                })}
              >
                  <PlusCircle className="w-4 h-4 mr-2" />
                  Adicionar Criptoativo
                </Button>
                </div>
                </>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name={`criptoativos.${index}.nome`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nome da Moeda</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name={`criptoativos.${index}.quantidade`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Quantidade</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" step="any" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name={`criptoativos.${index}.wallet`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Endereço da Wallet</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name={`criptoativos.${index}.exchange`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Exchange/Plataforma</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>
      ))}
    </Card>
  );

  const renderStep3 = () => (
    <Card className="p-6">
      <h2 className="text-2xl font-bold mb-4">Anotações Gerais</h2>
      
      <div className="space-y-4">
        <FormField
          control={form.control}
          name="anotacoesGerais"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Anotações</FormLabel>
              <FormControl>
                <Textarea 
                  {...field} 
                  rows={8}
                  placeholder="Digite aqui informações adicionais relevantes..."
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </Card>
  );

  const renderStep4 = () => (
    <Card className="p-6">
      <h2 className="text-2xl font-bold mb-4">Finalização</h2>
      
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="local"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Local</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="data"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Data</FormLabel>
                <FormControl>
                  <Input {...field} type="date" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      </div>
    </Card>
  );

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold">Contrato de Custódia de Criptoativos</h1>
          <Progress value={(currentStep / totalSteps) * 100} className="h-2" />
        </div>

        {currentStep === 1 && renderStep1()}
        {currentStep === 2 && renderStep2()}
        {currentStep === 3 && renderStep3()}
        {currentStep === 4 && renderStep4()}

        <div className="flex justify-between">
          {currentStep > 1 && (
            <Button type="button" variant="outline" onClick={handlePrevStep}>
              Voltar
            </Button>
            
          )}
          
          {currentStep < totalSteps ? (
            <Button type="button" onClick={handleNextStep} className="ml-auto">
              Próxima Etapa
            </Button>
          ) : (
            <Button type="submit" className="ml-auto">
              Gerar PDF
            </Button>
          )}
        </div>
      </form>
    </Form>
  );
};

export default ContractForm;