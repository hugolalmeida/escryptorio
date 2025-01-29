"use client";

// components/CryptoTracker.tsx
import React, { useState } from 'react';
import { Plus } from 'lucide-react';
import CryptoForm from './CryptoForm';
import CryptoCard from './CryptoCard';
import styles from '../styles/Crypto.module.css'

interface CryptoTransaction {
  id: number;
  name: string;
  symbol: string;
  quantity: number;
  buyPrice: number;
  currentPrice: number;
  date: string;
  exchange: string;
}

export default function CryptoTracker() {
  const [transactions, setTransactions] = useState<CryptoTransaction[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleAddTransaction = (transaction: Omit<CryptoTransaction, 'id'>) => {
    setTransactions(prev => [
      ...prev,
      {
        ...transaction,
        id: Date.now(),
      },
    ]);
    setIsModalOpen(false);
  };

  return (
    <div className={styles['crypto-container']}>
      <div className={styles['crypto-header']}>
        <h1 className={styles['crypto-title']}>Minhas Criptomoedas</h1>
        <button
          onClick={() => setIsModalOpen(true)}
          className={styles['add-button']}
        >
          <Plus size={24} />
        </button>
      </div>

      <div className={styles['crypto-grid']}>
        {transactions.map(transaction => (
          <CryptoCard
            key={transaction.id}
            transaction={transaction}
            onDelete={(id) => setTransactions(prev => prev.filter(t => t.id !== id))}
          />
        ))}
      </div>

      {isModalOpen && (
        <div className={styles['modal-overlay']}>
          <div className={styles['modal-content']}>
            <h2 className={styles['modal-title']}>Adicionar Nova Criptomoeda</h2>
            <CryptoForm onSubmit={handleAddTransaction} />
          </div>
        </div>
      )}
    </div>
  );
}