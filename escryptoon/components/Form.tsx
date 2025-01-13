"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const Form = () => {
  const [formData, setFormData] = useState({
    nome: "",
    email: "",
    mensagem: "",
  });

  const router = useRouter();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    // setPdfUrl(url); // Salva o URL do PDF gerado
    window.open(url, "_blank"); // Abre em uma nova aba

    // // Redireciona para a página de visualização com o PDF
    // router.push(`/visualizar?pdfUrl=${encodeURIComponent(url)}`);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input type="text" name="nome" placeholder="Nome" onChange={handleChange} required />
      <input type="email" name="email" placeholder="Email" onChange={handleChange} required />
      <textarea name="mensagem" placeholder="Mensagem" onChange={handleChange} required />
      <button type="submit">Visualizar PDF</button>
    </form>
  );
};

export default Form;
