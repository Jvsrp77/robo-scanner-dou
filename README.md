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

O gargalo é rede, não CPU: cada página é um download independente que passa a
maior parte do tempo esperando resposta. Por isso o paralelismo é por *threads*.

| Decisão | Por quê |
|---|---|
| **PyMuPDF** em vez de `pdfplumber` | Extração de texto mais rápida, e aceita o PDF como *stream* de bytes |
| **Leitura em memória** | Sem arquivo temporário: nada a limpar depois, e 400 PDFs não encostam no disco |
| **Sessão HTTP persistente** com retry (3 tentativas) em 500, 502, 503 e 504 | O servidor do DOU falha de forma intermitente sob carga |
| **6 threads com pausa de 0,2 s** | Rodando agendado todo dia, cinquenta conexões simultâneas contra um servidor público seriam padrão de abuso |
| **Extração separada do download** | A leitura do texto é função pura: testável com trechos salvos, sem depender do DOU estar no ar |

### Os dois formatos de registro

O analisador reconhece as duas formas em que a Seção 1 apresenta empresa e CNPJ:

```
RAZÃO SOCIAL LTDA / 00.000.000/0001-00        ← mesma linha, separados por barra

VENTO LESTE EDITORA E PUBLICACOES LTDA        ← razão social
CNPJ/CPF: 21.098.367/0001-60                  ← CNPJ rotulado, linha seguinte
```

O segundo é o que aparece nas edições atuais. Linhas que são campo rotulado
(`Processo:`, `Cidade:`, `Valor Aprovado:`) nunca são tomadas por razão social.

A análise percorre as páginas **na ordem do jornal**, carregando o registro em
aberto de uma para a outra: empresa cujo bloco começa no fim de uma página e
termina na seguinte deixa de sair incompleta. Se houver buraco na sequência —
página que falhou ou não existe — o registro é fechado como está, porque o
trecho perdido não pode ser inventado.

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

20 testes, nenhum acessa a rede. Cobrem o reconhecimento de empresa e CNPJ, o
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

- **Razão social quebrada em duas linhas sai cortada.** Quando o PDF quebra o
  nome no meio, só o trecho vizinho ao CNPJ é capturado — aparecem registros
  como `INSTITUTO E` ou `AURORA REC`. Numa amostra de 234 registros, cerca de
  uma dúzia saiu assim.
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
