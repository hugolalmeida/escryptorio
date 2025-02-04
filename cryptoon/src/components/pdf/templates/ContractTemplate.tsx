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

// Estilos para o PDF
const styles = StyleSheet.create({
  page: {
    padding: 40,
    backgroundColor: '#ffffff',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
    borderBottom: 1,
    borderBottomColor: '#112233',
    paddingBottom: 10,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#112233',
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
    backgroundColor: '#f0f0f0',
    padding: 5,
  },
  field: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  label: {
    width: '30%',
    fontSize: 12,
    fontWeight: 'bold',
  },
  value: {
    width: '70%',
    fontSize: 12,
  },
  cryptoSection: {
    marginBottom: 15,
    padding: 10,
    backgroundColor: '#f9f9f9',
  },
  cryptoTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  notes: {
    marginTop: 20,
    padding: 10,
    backgroundColor: '#f5f5f5',
  },
  signature: {
    marginTop: 30,
    borderTop: 1,
    borderTopColor: '#112233',
    paddingTop: 10,
  },
  pageNumber: {
    position: 'absolute',
    bottom: 30,
    right: 30,
    fontSize: 10,
  },
});

const CryptoDocument = ({ data }) => (
  <Document>
    <Page style={styles.page}>
      <View style={styles.header}>
        <Image 
          src="/logo.png" 
          style={{ width: 100 }} 
        />
        <Text style={styles.title}>Ficha de Levantamento de Criptoativos</Text>
      </View>

      {/* Dados do Proprietário */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Dados do Proprietário</Text>
        <View style={styles.field}>
          <Text style={styles.label}>Nome Completo:</Text>
          <Text style={styles.value}>{data.nome}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>CPF/CNPJ:</Text>
          <Text style={styles.value}>{data.cpfCnpj}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Rua:</Text>
          <Text style={styles.value}>{data.endereco.rua}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Número:</Text>
          <Text style={styles.value}>{data.endereco.numero}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Complemento:</Text>
          <Text style={styles.value}>{data.endereco.complemento}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Bairro:</Text>
          <Text style={styles.value}>{data.endereco.bairro}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Cidade:</Text>
          <Text style={styles.value}>{data.endereco.cidade}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Estado:</Text>
          <Text style={styles.value}>{data.endereco.estado}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>CEP:</Text>
          <Text style={styles.value}>{data.endereco.cep}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Telefone:</Text>
          <Text style={styles.value}>{data.telefone}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>E-mail:</Text>
          <Text style={styles.value}>{data.email}</Text>
        </View>
      </View>

      {/* Informações dos Criptoativos */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Informações dos Criptoativos</Text>
        {data.criptoativos.map((crypto, index) => (
          <View key={index} style={styles.cryptoSection}>
            <Text style={styles.cryptoTitle}>{index + 1}. Criptoativo</Text>
            <View style={styles.field}>
              <Text style={styles.label}>Nome da Moeda:</Text>
              <Text style={styles.value}>{crypto.nome}</Text>
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>Quantidade:</Text>
              <Text style={styles.value}>{crypto.quantidade}</Text>
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>Endereço da Wallet:</Text>
              <Text style={styles.value}>{crypto.wallet}</Text>
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>Exchange:</Text>
              <Text style={styles.value}>{crypto.exchange}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Anotações */}
      {data.anotacoes && (
        <View style={styles.notes}>
          <Text style={styles.sectionTitle}>Anotações Gerais</Text>
          <Text>{data.anotacoes}</Text>
        </View>
      )}

      {/* Assinatura */}
      <View style={styles.signature}>
        <View style={styles.field}>
          <Text style={styles.label}>Local:</Text>
          <Text style={styles.value}>{data.local}</Text>
        </View>
        <View style={styles.field}>
          <Text style={styles.label}>Data:</Text>
          <Text style={styles.value}>{data.data}</Text>
        </View>
      </View>

      <Text style={styles.pageNumber} render={({ pageNumber, totalPages }) => (
        `${pageNumber} / ${totalPages}`
      )} fixed />
    </Page>
  </Document>
);

export default CryptoDocument;