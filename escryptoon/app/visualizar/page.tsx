"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function VisualizarPage() {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    // Pega o URL do PDF da query string
    const params = new URLSearchParams(window.location.search);
    const url = params.get("pdfUrl");

    if (!url) {
      router.push("/formulario"); // Redireciona se não tiver URL
    } else {
      setPdfUrl(url);
    }
  }, [router]);

  if (!pdfUrl) {
    return <p>Carregando...</p>;
  }

  return (
    <div>
      <h1>Visualização do PDF</h1>
      <iframe src={pdfUrl} width="100%" height="500px" />
      <a href={pdfUrl} download="documento.pdf">
        <button>Baixar PDF</button>
      </a>
    </div>
  );
}
