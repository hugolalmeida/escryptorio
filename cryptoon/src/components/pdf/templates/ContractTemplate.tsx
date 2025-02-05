// components/pdf/templates/ContractTemplate.tsx
'use client';

import React from 'react';
import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Image
} from '@react-pdf/renderer';

const styles = StyleSheet.create({
  page: {
    padding: '40 30',
    fontSize: 11,
    fontFamily: 'Helvetica',
    backgroundColor: '#ffffff',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
    borderBottom: '1pt solid #000000',
    paddingBottom: 10,
  },
  logoContainer: {
    width: 150,
    height: 60,
    border: '1pt solid #000000',
    marginRight: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoText: {
    width: 100,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 10,
    borderBottom: '1pt solid #000000',
    paddingBottom: 4,
  },
  table: {
    display: 'table',
    width: 'auto',
    marginBottom: 10,
    borderStyle: 'solid',
    borderColor: '#000000',
    borderWidth: 1,
  },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#000000',
    borderBottomStyle: 'solid',
    minHeight: 25,
    alignItems: 'center',
  },
  tableCol: {
    borderRightWidth: 1,
    borderRightColor: '#000000',
    borderRightStyle: 'solid',
    paddingLeft: 5,
    paddingRight: 5,
    paddingTop: 3,
    paddingBottom: 3,
  },
  tableLabel: {
    width: '20%',
    backgroundColor: '#ffffff',
    fontWeight: 'bold',
  },
  tableValue: {
    width: '80%',
  },
  tableCellHalf: {
    width: '50%',
  },
  tableCellQuarter: {
    width: '25%',
  },
  cryptoTable: {
    marginTop: 10,
    marginBottom: 20,
  },
  cryptoHeader: {
    backgroundColor: '#ffffff',
    fontWeight: 'bold',
  },
  cryptoCell: {
    width: '23%',
    borderRightWidth: 1,
    borderRightColor: '#000000',
    borderRightStyle: 'solid',
    paddingLeft: 5,
    paddingRight: 5,
    paddingTop: 3,
    paddingBottom: 3,
  },
  cryptoIndexCell: {
    width: '8%',
    borderRightWidth: 1,
    borderRightColor: '#000000',
    borderRightStyle: 'solid',
    paddingLeft: 5,
    paddingRight: 5,
    paddingTop: 3,
    paddingBottom: 3,
  },
  notes: {
    marginTop: 10,
    marginBottom: 20,
  },
  notesContent: {
    border: '1pt solid #000000',
    padding: 8,
    minHeight: 60,
  },
  footer: {
    marginTop: 30,
  },
  dateLocation: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 50,
  },
  signature: {
    alignItems: 'center',
  },
  signatureLine: {
    borderTop: '1pt solid #000000',
    width: '60%',
    marginBottom: 5,
  },
  signatureText: {
    fontSize: 11,
  },
});

interface Address {
  rua: string;
  numero: string;
  complemento: string;
  bairro: string;
  cep: string;
  cidade: string;
  estado: string;
}

interface Crypto {
  nome: string;
  quantidade: string;
  wallet: string;
  exchange: string;
}

interface Data {
  nome: string;
  cpfCnpj: string;
  endereco: Address;
  telefone: string;
  email: string;
  criptoativos: Crypto[];
  anotacoesGerais: string;
  local: string;
  data: string;
}

const ContractTemplate = ({ data }: { data: Data }) => (
  <Document>
    <Page style={styles.page}>
      {/* Header */}
      <View style={styles.header}>
          <Image style={styles.logoText} src="/logo.jpg" />
        <Text style={styles.headerTitle}>Ficha de Levantamento de Criptoativos</Text>
      </View>

      {/* Dados do Proprietário */}
      <Text style={styles.sectionTitle}>Dados do Proprietário</Text>
      <View style={styles.table}>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Nome Completo:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableValue]}>
            <Text>{data.nome}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>CPF/CNPJ:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableValue]}>
            <Text>{data.cpfCnpj}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Endereço:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableValue]}>
            <Text>{`${data.endereco.rua}, ${data.endereco.numero}`}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Complemento:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableValue]}>
            <Text>{data.endereco.complemento}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Bairro:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.endereco.bairro}</Text>
          </View>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>CEP:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.endereco.cep}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Cidade:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.endereco.cidade}</Text>
          </View>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Estado:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.endereco.estado}</Text>
          </View>
        </View>
        <View style={styles.tableRow}>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>Telefone:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.telefone}</Text>
          </View>
          <View style={[styles.tableCol, styles.tableLabel]}>
            <Text>E-mail:</Text>
          </View>
          <View style={[styles.tableCol, styles.tableCellHalf]}>
            <Text>{data.email}</Text>
          </View>
        </View>
      </View>

      {/* Informações dos Criptoativos */}
      <Text style={styles.sectionTitle}>Informações dos Criptoativos</Text>
      <View style={[styles.table, styles.cryptoTable]}>
        <View style={styles.tableRow}>
          <View style={[styles.cryptoIndexCell, styles.cryptoHeader]}>
            <Text>Nº</Text>
          </View>
          <View style={[styles.cryptoCell, styles.cryptoHeader]}>
            <Text>Nome da Moeda</Text>
          </View>
          <View style={[styles.cryptoCell, styles.cryptoHeader]}>
            <Text>Quantidade</Text>
          </View>
          <View style={[styles.cryptoCell, styles.cryptoHeader]}>
            <Text>Endereço da Wallet</Text>
          </View>
          <View style={[styles.cryptoCell, styles.cryptoHeader]}>
            <Text>Exchange/Plataforma</Text>
          </View>
        </View>
        {data.criptoativos.map((crypto, index) => (
          <View key={index} style={styles.tableRow}>
            <View style={styles.cryptoIndexCell}>
              <Text>{index + 1}</Text>
            </View>
            <View style={styles.cryptoCell}>
              <Text>{crypto.nome}</Text>
            </View>
            <View style={styles.cryptoCell}>
              <Text>{crypto.quantidade}</Text>
            </View>
            <View style={styles.cryptoCell}>
              <Text>{crypto.wallet}</Text>
            </View>
            <View style={styles.cryptoCell}>
              <Text>{crypto.exchange}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Anotações */}
      <Text style={styles.sectionTitle}>Anotações Gerais</Text>
      <View style={styles.notesContent}>
        <Text>{data.anotacoesGerais}</Text>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <View style={styles.dateLocation}>
          <Text>Local: {data.local}</Text>
          <Text>Data: {data.data}</Text>
        </View>
        <View style={styles.signature}>
          <View style={styles.signatureLine} />
          <Text style={styles.signatureText}>Assinatura do Proprietário</Text>
        </View>
      </View>
    </Page>
  </Document>
);

export default ContractTemplate;