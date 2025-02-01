// src/components/shared/BackButton.tsx
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export const BackButton = ({ href }: { href: string }) => {
  return (
    <Link 
      href={href}
      className="absolute top-4 left-4 flex items-center text-gray-600 hover:text-gray-900"
    >
      <ArrowLeft className="w-5 h-5 mr-1" />
      Voltar
    </Link>
  );
};