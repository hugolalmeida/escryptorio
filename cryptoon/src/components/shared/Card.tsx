// src/components/shared/Card.tsx
import React, { ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  footer?: ReactNode;
}

export const Card: React.FC<CardProps> = ({ 
  children, 
  className, 
  title, 
  footer 
}) => {
  return (
    <div 
      className={twMerge(
        'bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden',
        className
      )}
    >
      {title && (
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        </div>
      )}
      
      <div className="p-4">
        {children}
      </div>
      
      {footer && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          {footer}
        </div>
      )}
    </div>
  );
};