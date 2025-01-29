"use client";

// components/CryptoCard.tsx
import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import styles from '../styles/Crypto.module.css'



export default function CryptoCard({ transaction, onDelete }) {
    const [showDetails, setShowDetails] = useState(false);
    const profitLoss = calculateProfitLoss(transaction);
    const profitLossPercentage = calculateProfitLossPercentage(transaction);
  
    function calculateProfitLoss(transaction) {
      const currentPrice = transaction.purchasePrice * 1.1;
      return (currentPrice - transaction.purchasePrice) * transaction.amount;
    }
  
    function calculateProfitLossPercentage(transaction) {
      const currentPrice = transaction.purchasePrice * 1.1;
      return ((currentPrice - transaction.purchasePrice) / transaction.purchasePrice) * 100;
    }
  
    return (
      <>
        <button
          onClick={() => setShowDetails(true)}
          className={styles['crypto-card']}
        >
          <div className={styles['crypto-symbol']}>{transaction.symbol}</div>
          <div className={styles['crypto-name']}>{transaction.name}</div>
          <div className={profitLoss >= 0 ? styles.profit : styles.loss}>
            {profitLossPercentage.toFixed(2)}%
          </div>
          <div className={styles['crypto-amount']}>
            Quantidade: {transaction.amount}
          </div>
        </button>
  
        {showDetails && (
          <div
            className={styles['modal-overlay']}
            onClick={() => setShowDetails(false)}
          >
            <div
              className={styles['modal-content']}
              onClick={e => e.stopPropagation()}
            >
              <div className={styles['crypto-details']}>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Nome:</span>
                  <span className={styles['detail-value']}>{transaction.name}</span>
                </div>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Símbolo:</span>
                  <span className={styles['detail-value']}>{transaction.symbol}</span>
                </div>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Quantidade:</span>
                  <span className={styles['detail-value']}>{transaction.amount}</span>
                </div>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Preço de Compra:</span>
                  <span className={styles['detail-value']}>${transaction.purchasePrice}</span>
                </div>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Data de Compra:</span>
                  <span className={styles['detail-value']}>{transaction.purchaseDate}</span>
                </div>
                <div className={styles['detail-row']}>
                  <span className={styles['detail-label']}>Lucro/Prejuízo:</span>
                  <span className={profitLoss >= 0 ? styles.profit : styles.loss}>
                    ${profitLoss.toFixed(2)}
                  </span>
                </div>
              </div>
              <button
                onClick={() => onDelete(transaction.id)}
                className={styles['delete-button']}
              >
                <Trash2 size={20} />
              </button>
            </div>
          </div>
        )}
      </>
    );
  }