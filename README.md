# 🤖 Robô Scanner DOU — Edição Fórmula 1

> Automação de alta velocidade para monitoramento de publicações no **Diário Oficial da União (DOU)**, com download paralelo, extração de texto em PDF e geração de relatório Excel formatado.

---

## 📋 Sobre o Projeto

Este robô varre automaticamente as páginas da **Seção 1 do DOU** todos os dias, extrai dados de empresas (nome, CNPJ, atividades autorizadas e status), e consolida tudo em um relatório `.xlsx` com destaque visual — pronto para análise regulatória, due diligence ou monitoramento de concorrentes.

Desenvolvido com foco em **velocidade máxima**: enquanto soluções tradicionais levariam minutos, este robô processa centenas de páginas em segundos.

---

## ⚡ Destaques Técnicos

| Otimização | Tecnologia | Benefício |
|---|---|---|
| Motor de PDF | **PyMuPDF (fitz)** | Extração instantânea vs. pdfplumber |
| Conexão HTTP | **Sessão persistente + Retry** | Sem overhead de reconexão |
| Paralelismo | **50 Threads simultâneas** | 50x mais rápido que sequencial |
| Saída | **openpyxl + pandas** | Relatório Excel pronto para uso |

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.x**
- `PyMuPDF (fitz)` — leitura de PDF direto da memória
- `requests` + `urllib3` — download com retry automático
- `concurrent.futures` — paralelismo com ThreadPoolExecutor
- `pandas` — manipulação e exportação de dados
- `openpyxl` — formatação do Excel (cabeçalho amarelo)
- `re` (regex) — extração de CNPJ, nome e atividades

---

## 🚀 Como Usar

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/robo-scanner-dou.git
cd robo-scanner-dou
```

### 2. Instale as dependências
```bash
pip install pymupdf pandas requests openpyxl
```

### 3. Execute
```bash
python robo_dou.py
```

O relatório será salvo automaticamente como:
```
Relatorio_Geral_DD-MM-AAAA.xlsx
```

---

## ⚙️ Configurações

Edite as variáveis no topo do script para personalizar:

```python
# Data manual (opcional — padrão é o dia atual)
# DATA_ALVO = "08/12/2025"

JORNAL_ID = 515        # Seção 1 do DOU
PAGINA_INICIAL = 1
PAGINA_FINAL = 400     # Limite de varredura
THREADS = 50           # Downloads simultâneos
```

---

## 📊 Estrutura do Relatório Gerado

| Campo | Descrição |
|---|---|
| Data | Data da publicação |
| Página | Página do DOU onde foi encontrado |
| Empresa | Razão social |
| CNPJ | CNPJ extraído automaticamente |
| Atividades | Atividades autorizadas (ARMAZENAR, DISTRIBUIR, etc.) |
| Status | LIBERADA / INDEFERIDO / Em Análise |
| Link | Link direto para a publicação no DOU |

---

## 🔍 Como Funciona (Arquitetura)

```
┌─────────────────────────────────────────────┐
│              robo_turbo_max()               │
│  Dispara 50 threads para páginas do DOU     │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │ processar_pagina() │  ← por thread
         │  1. GET /pdf       │
         │  2. fitz.open()    │
         │  3. Regex CNPJ     │
         │  4. Extrai dados   │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │   Consolida tudo   │
         │   Gera .xlsx       │
         │   Pinta cabeçalho  │
         └────────────────────┘
```

---

## 📈 Performance

- ✅ ~400 páginas processadas em **menos de 30 segundos**
- ✅ Tolerante a falhas (retry automático em erros 5xx)
- ✅ Sem dependência de arquivos temporários (tudo em memória)

---

## 🤝 Contribuições

Sugestões, melhorias e PRs são bem-vindos! Abra uma *issue* ou entre em contato.

---

## 📄 Licença

MIT License — fique à vontade para usar e adaptar.

---

*Desenvolvido com Python 🐍 | Dados públicos do [Diário Oficial da União](https://www.in.gov.br)*
