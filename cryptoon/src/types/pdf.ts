interface Endereco {
    rua: string;
    numero: string;
    complemento: string;
    bairro: string;
    cidade: string;
    estado: string;
    cep: string;
  }
  
  interface Criptoativo {
    nome: string;
    quantidade: string;
    wallet: string;
    exchange: string;
  }
  
  interface DocumentData {
    nome: string;
    cpfCnpj: string;
    endereco: Endereco;
    telefone: string;
    email: string;
    criptoativos: Criptoativo[];
    anotacoes?: string;
    local: string;
    data: string;
  }