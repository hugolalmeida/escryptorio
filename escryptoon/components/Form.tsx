"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from '../styles/Form.module.css';
import { Plus, Trash2 } from 'lucide-react';

interface CryptoAsset {
  id: number;
  coinName: string;
  quantity: string;
  walletAddress: string;
  exchange: string;
}

const Form = () => {
  const [currentStep, setCurrentStep] = useState<1 | 2>(1);
  const [cryptoAssets, setCryptoAssets] = useState<CryptoAsset[]>([
    { id: 1, coinName: '', quantity: '', walletAddress: '', exchange: '' }
  ]);
  
  const [formData, setFormData] = useState({
    // Dados Pessoais
    nomeCompleto: "",
    cpfCnpj: "",
    rua: "",
    numero: "",
    complemento: "",
    bairro: "",
    cidade: "",
    estado: "",
    cep: "",
    telefone: "",
    email: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleCryptoChange = (id: number, field: keyof CryptoAsset, value: string) => {
    setCryptoAssets(assets => 
      assets.map(asset => 
        asset.id === id ? { ...asset, [field]: value } : asset
      )
    );
  };

  const addCryptoAsset = () => {
    const newId = Math.max(...cryptoAssets.map(asset => asset.id)) + 1;
    setCryptoAssets([...cryptoAssets, { 
      id: newId, 
      coinName: '', 
      quantity: '', 
      walletAddress: '', 
      exchange: '' 
    }]);
  };

  const removeCryptoAsset = (id: number) => {
    if (cryptoAssets.length > 1) {
      setCryptoAssets(assets => assets.filter(asset => asset.id !== id));
    }
  };

  const handleNextStep = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentStep(2);
  };

  const handlePrevStep = () => {
    setCurrentStep(1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const completeData = {
      ...formData,
      cryptoAssets
    };

    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(completeData),
    });

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");
  };

  const renderStep1 = () => (
    <div className={styles.formStep}>
      <h2>Dados do Proprietário</h2>
      
      <div className={styles.formGrid}>
        <div className={styles.formGroup}>
          <label htmlFor="nomeCompleto">Nome Completo</label>
          <input
            id="nomeCompleto"
            type="text"
            name="nomeCompleto"
            value={formData.nomeCompleto}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
          <label htmlFor="cpfCnpj">CPF/CNPJ</label>
          <input
            id="cpfCnpj"
            type="text"
            name="cpfCnpj"
            value={formData.cpfCnpj}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroupFull}>
        <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="telefone">Telefone</label>
          <input
            id="telefone"
            type="tel"
            name="telefone"
            value={formData.telefone}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="rua">Rua</label>
          <input
            id="rua"
            type="text"
            name="rua"
            value={formData.rua}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="numero">Número</label>
          <input
            id="numero"
            type="text"
            name="numero"
            value={formData.numero}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="complemento">Complemento</label>
          <input
            id="complemento"
            type="text"
            name="complemento"
            value={formData.complemento}
            onChange={handleChange}
          />
          
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="bairro">Bairro</label>
          <input
            id="bairro"
            type="text"
            name="bairro"
            value={formData.bairro}
            onChange={handleChange}
            required
          />
          
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="cidade">Cidade</label>
          <input
            id="cidade"
            type="text"
            name="cidade"
            value={formData.cidade}
            onChange={handleChange}
            required
          />
          
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="estado">Estado</label>
          <input
            id="estado"
            type="text"
            name="estado"
            value={formData.estado}
            onChange={handleChange}
            required
          />
        </div>

        <div className={styles.formGroup}>
        <label htmlFor="cep">CEP</label>
          <input
            id="cep"
            type="text"
            name="cep"
            value={formData.cep}
            onChange={handleChange}
            required
          />
        </div>
      </div>

      <button type="button" onClick={handleNextStep} className={styles.nextButton}>
        Próxima Etapa
      </button>
    </div>
  );

  const renderStep2 = () => (
    <div className={styles.formStep}>
      <h2>Informações dos Criptoativos</h2>

      {cryptoAssets.map((asset, index) => (
        <div key={asset.id} className={styles.cryptoAssetContainer}>
          <h3>Criptoativo {index + 1}</h3>
          
          <div className={styles.cryptoAssetGrid}>
            <div className={styles.formGroup}>
              <label>Nome da Moeda</label>
              <input
                type="text"
                value={asset.coinName}
                onChange={(e) => handleCryptoChange(asset.id, 'coinName', e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>Quantidade</label>
              <input
                type="text"
                value={asset.quantity}
                onChange={(e) => handleCryptoChange(asset.id, 'quantity', e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>Endereço da Wallet</label>
              <input
                type="text"
                value={asset.walletAddress}
                onChange={(e) => handleCryptoChange(asset.id, 'walletAddress', e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>Exchange/Plataforma</label>
              <input
                type="text"
                value={asset.exchange}
                onChange={(e) => handleCryptoChange(asset.id, 'exchange', e.target.value)}
                required
              />
            </div>

            {cryptoAssets.length > 1 && (
              <button
                type="button"
                onClick={() => removeCryptoAsset(asset.id)}
                className={styles.removeButton}
              >
                <Trash2 size={20} />
              </button>
            )}
          </div>
        </div>
      ))}

      <button type="button" onClick={addCryptoAsset} className={styles.addButton}>
        <Plus size={20} /> Adicionar Criptoativo
      </button>

      <div className={styles.buttonGroup}>
        <button type="button" onClick={handlePrevStep} className={styles.prevButton}>
          Voltar
        </button>
        <button type="submit" className={styles.submitButton}>
          Gerar PDF
        </button>
      </div>
    </div>
  );

  return (
    <div className={styles.formContainer}>
      <h1 className={styles.mainTitle}>Ficha de Levantamento de Criptoativos</h1>
      
      <div className={styles.progressBar}>
        <div 
          className={styles.progress}
          style={{ width: currentStep === 1 ? '50%' : '100%' }}
        />
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        {currentStep === 1 ? renderStep1() : renderStep2()}
      </form>
    </div>
  );
};

export default Form;