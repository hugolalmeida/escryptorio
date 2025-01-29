"use client";

// components/CryptoForm.tsx
import React, { useState } from 'react';
import styles from '../styles/Crypto.module.css'

export default function CryptoForm({ onSubmit }) {
    const [formData, setFormData] = useState({
      name: '',
      symbol: '',
      amount: '',
      purchasePrice: '',
      purchaseDate: '',
    });
  
    const handleSubmit = (e: { preventDefault: () => void; }) => {
      e.preventDefault();
      onSubmit(formData);
      setFormData({
        name: '',
        symbol: '',
        amount: '',
        purchasePrice: '',
        purchaseDate: '',
      });
    };
  
    const handleInputChange = (e: { target: { name: any; value: any; }; }) => {
      const { name, value } = e.target;
      setFormData(prev => ({ ...prev, [name]: value }));
    };
  
    return (
      <form onSubmit={handleSubmit} className={styles['crypto-form']}>
        <div className={styles['form-grid']}>
          <div className={styles['form-group']}>
            <label className={styles['form-label']}>Nome da Cripto</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              className={styles['form-input']}
              required
            />
          </div>
          <div className={styles['form-group']}>
            <label className={styles['form-label']}>Símbolo</label>
            <input
              type="text"
              name="symbol"
              value={formData.symbol}
              onChange={handleInputChange}
              className={styles['form-input']}
              required
            />
          </div>
          <div className={styles['form-group']}>
            <label className={styles['form-label']}>Quantidade</label>
            <input
              type="number"
              name="amount"
              value={formData.amount}
              onChange={handleInputChange}
              className={styles['form-input']}
              required
            />
          </div>
          <div className={styles['form-group']}>
            <label className={styles['form-label']}>Preço de Compra (USD)</label>
            <input
              type="number"
              name="purchasePrice"
              value={formData.purchasePrice}
              onChange={handleInputChange}
              className={styles['form-input']}
              required
            />
          </div>
          <div className={styles['form-group']}>
            <label className={styles['form-label']}>Data de Compra</label>
            <input
              type="date"
              name="purchaseDate"
              value={formData.purchaseDate}
              onChange={handleInputChange}
              className={styles['form-input']}
              required
            />
          </div>
        </div>
        <div className={styles['form-buttons']}>
          <button type="submit" className={styles['submit-button']}>
            Adicionar
          </button>
        </div>
      </form>
    );
  }