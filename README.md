# Robô Scanner DOU

Monitor automatizado de autorizações publicadas na **Seção 1 do Diário Oficial da União**. Varre as páginas do dia, extrai as empresas citadas com CNPJ, atividades autorizadas e situação do pedido, e consolida tudo num relatório `.xlsx`.

Feito para quem precisa acompanhar diariamente concessões e indeferimentos de autorização de funcionamento — monitoramento regulatório, *due diligence* e acompanhamento de concorrentes. O trabalho manual equivalente é abrir centenas de PDFs à mão, todo dia.

## O que o projeto faz

1. Monta a URL de cada página do DOU para a data informada e baixa o PDF.
2. Lê o texto **direto da memória**, sem gravar arquivo temporário em disco.
3. Identifica os registros por expressão regular no padrão `RAZÃO SOCIAL / 00.000.000/0000-00`.
4. Para cada empresa encontrada, acumula as atividades autorizadas (`ARMAZENAR`, `DISTRIBUIR`, `EXPEDIR`, `TRANSPORTAR`, `COMÉRCIO`, `FABRICAR`, `IMPORTAR`, `DISPENSAR`) e classifica a situação em `LIBERADA`, `INDEFERIDO` ou `Em Análise`.
5. Ordena os resultados por página, gera o Excel e destaca o cabeçalho.

As páginas são baixadas por **50 threads simultâneas**, cobrindo por padrão até **400 páginas** — os dois números são configuráveis.

## Como funciona

O gargalo aqui é rede, não CPU: cada página é um download independente que passa a maior parte do tempo esperando resposta do servidor. Por isso o paralelismo é por *threads*, e não por processos.

| Decisão | Por quê |
|---|---|
| **PyMuPDF** (`fitz`) em vez de `pdfplumber` | Extração de texto consideravelmente mais rápida, e aceita o PDF como *stream* de bytes |
| **Leitura em memória** (`fitz.open(stream=...)`) | Sem arquivo temporário: nada a limpar depois, e 400 PDFs não encostam no disco |
| **Sessão HTTP persistente** com pool dimensionado para as 50 threads | Evita refazer handshake TLS a cada página |
| **Retry automático** (3 tentativas, *backoff* 0,1) em erros 500, 502, 503 e 504 | O servidor do DOU falha de forma intermitente sob carga |
| **`ThreadPoolExecutor` + `as_completed`** | Processa cada resultado assim que chega, em vez de esperar o lote inteiro |
| **Ordenação por página no fim** | `as_completed` devolve fora de ordem; o relatório precisa sair na ordem do jornal |

A extração usa um analisador de linhas com estado: quando uma linha casa com o padrão de CNPJ, abre-se um registro novo; as linhas seguintes são acumuladas como atividade ou situação até que o próximo CNPJ apareça. É simples de propósito — o texto do DOU não tem estrutura para justificar um analisador mais pesado.

## Stack

- **Python 3.10+**
- `PyMuPDF` — leitura de PDF a partir da memória
- `requests` + `urllib3` — sessão persistente com retry
- `concurrent.futures` — paralelismo por threads
- `pandas` — consolidação e exportação
- `openpyxl` — formatação do Excel

## Como rodar

```bash
git clone https://github.com/Jvsrp77/robo-scanner-dou.git
cd robo-scanner-dou
pip install -r requirements.txt
python robo_dou.py
```

O relatório é salvo na pasta atual como `Relatorio_Geral_DD-MM-AAAA.xlsx`. Se já existir um arquivo com o nome do dia, os novos registros são anexados ao final em vez de sobrescrevê-lo.

## Configuração

As variáveis ficam no topo do script:

```python
DATA_ALVO = datetime.datetime.now().strftime("%d/%m/%Y")   # padrão: hoje
JORNAL_ID = 515        # Seção 1 do DOU
PAGINA_INICIAL = 1
PAGINA_FINAL = 400     # limite de varredura
THREADS = 50           # downloads simultâneos
```

Para varrer uma data passada, fixe `DATA_ALVO` no formato `"DD/MM/AAAA"`.

## O relatório

| Campo | Conteúdo |
|---|---|
| Data | Data da publicação |
| Página | Página do DOU onde o registro foi encontrado |
| Empresa | Razão social, já sem a numeração do item |
| CNPJ | Extraído por expressão regular |
| Atividades | Atividades autorizadas, separadas por ` \| ` |
| Status | `LIBERADA`, `INDEFERIDO` ou `Em Análise` |
| Link | Endereço da página no portal do DOU |

## Limitações conhecidas

Registradas por transparência — são os pontos que eu trataria antes de considerar isto pronto para produção:

- **Falhas são silenciosas.** Página que não baixa devolve lista vazia, igual a uma página sem empresas. Não dá para distinguir "não achou nada" de "o download falhou", e os `except` genéricos engolem a causa. O correto seria registrar o erro por página e informar quantas falharam ao fim.
- **50 threads contra um servidor público é agressivo.** Não há limite de taxa nem intervalo entre requisições. Para uso recorrente, vale reduzir o paralelismo ou espaçar as chamadas — o retry trata a falha, mas não evita causá-la.
- **Registro dividido entre duas páginas se perde.** Cada página é analisada isoladamente, então uma empresa cujo bloco começa no fim de uma página e termina na seguinte sai incompleta.
- **A classificação de situação é por palavra-chave.** `DEFERIDO`, `CONCESSÃO`, `AUTORIZA` e `INDEFERIDO` são procurados na linha crua. Texto com negação ou redação fora do padrão pode ser classificado errado.
- **Configuração por edição do arquivo.** Sem argumentos de linha de comando, o que atrapalha agendar execuções com datas diferentes.
- **Sem testes.**

## Licença

[MIT](LICENSE)
