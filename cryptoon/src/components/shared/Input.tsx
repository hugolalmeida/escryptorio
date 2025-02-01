// src/components/shared/Input.tsx
import React, { InputHTMLAttributes } from 'react';
import { twMerge } from 'tailwind-merge';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  className?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  className,
  ...props
}) => {
  return (
    <div className="w-full">
      {label && (
        <label 
          className="block text-sm font-medium text-gray-700 mb-1"
          htmlFor={props.id}
        >
          {label}
        </label>
      )}
      <input
        className={twMerge(
          'block w-full px-3 py-2 border rounded-md shadow-sm text-white',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
          error ? 'border-red-500 text-red-900' : 'border-gray-300',
          className
        )}
        {...props}
      />
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};