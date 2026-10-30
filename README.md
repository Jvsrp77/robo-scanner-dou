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
- `pandas` + `openpyxl` — consolidação e formatação do Excel
- `pytest` — testes da extração e da gravação

## Estrutura

A extração não faz rede nem disco: recebe texto e devolve registros. É o que
permite testá-la com trechos salvos, sem depender do DOU estar no ar.

```
robo_dou.py          ponto de entrada e resumo da execução
dou/
├── config.py        argumentos de linha de comando e variáveis de ambiente
├── coleta.py        download e extração do texto do PDF
├── extracao.py      leitura do texto (função pura, testável)
└── saida.py         gravação do Excel
tests/
├── test_extracao.py
└── test_saida.py
```

## Como rodar

```bash
git clone https://github.com/Jvsrp77/robo-scanner-dou.git
cd robo-scanner-dou
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python robo_dou.py                                   # edição de hoje
python robo_dou.py --data 08/12/2025                 # edição passada
python robo_dou.py --threads 4 --pagina-final 120    # varredura menor
```

| Argumento | Padrão | O que faz |
|---|---|---|
| `--data` | hoje | Edição a varrer, em `DD/MM/AAAA` |
| `--pagina-inicial` / `--pagina-final` | 1 / 400 | Intervalo de páginas |
| `--threads` | 6 | Downloads simultâneos |
| `--pausa` | 0,2 s | Intervalo entre requisições |
| `--saida` | `.` | Pasta do relatório |

Também aceita `DOU_PAGINA_FINAL`, `DOU_THREADS`, `DOU_SAIDA` e `DOU_JORNAL_ID`
por variável de ambiente, para agendamento.

**O processo termina com código 1 se alguma página falhou.** Pipeline que falha
em silêncio é pior que pipeline que quebra.

```
 400 páginas solicitadas
 382 com PDF válido
  18 sem PDF (fim da seção)
   0 com erro de rede ou leitura
 127 registros extraídos (3 continuavam na página seguinte)
```

## Testes

```bash
pytest
```

15 testes, nenhum acessa a rede. Cobrem o reconhecimento de empresa e CNPJ, o
acúmulo de atividades, a classificação de situação (incluindo o caso em que
`INDEFERIDO` contém `DEFERIDO`), a costura de registro partido entre páginas e
a gravação do Excel — entre eles um que simula falha de escrita e confere que o
relatório anterior **não** foi destruído.

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

Registradas por transparência:

- **O padrão de reconhecimento não casa com o DOU atual.** A expressão regular
  espera `RAZÃO SOCIAL / 00.000.000/0000-00` na mesma linha. Varrendo as edições
  de 08/12/2025, 27/10/2026 e 29/10/2026, encontrei **861, 184 e 335 linhas com
  CNPJ e nenhuma nesse formato** — o texto atual traz `CNPJ/CPF: 00.000.000/0001-00`
  numa linha própria, com a razão social na linha anterior. Enquanto isso não for
  tratado, a extração devolve zero registros nessas edições.
- **A classificação de situação é por palavra-chave.** `DEFERIDO`, `CONCESSÃO`,
  `AUTORIZA` e `INDEFERIDO` são procurados na linha crua. Redação fora do padrão
  pode ser classificada errado.
- **O destino é um Excel por dia.** Para histórico e consulta, o caminho é banco
  de dados — é o próximo passo do projeto.
- **A costura entre páginas não atravessa buraco.** Se a página do meio falhou
  ou não existe, o registro aberto é fechado como está, porque o trecho perdido
  não pode ser inventado.

## Licença

[MIT](LICENSE)
