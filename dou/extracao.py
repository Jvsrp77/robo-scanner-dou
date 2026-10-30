"""Leitura do texto do DOU.

Esta camada nao faz rede nem disco: recebe texto e devolve registros.
E o que permite testa-la com trechos salvos, sem depender do DOU estar no ar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Rotulos que abrem linha de atividade nas publicacoes de autorizacao
# sanitaria. Mais largo que VERBOS_ATIVIDADE porque o texto da ANVISA usa
# formas que o conjunto original nao previa.
VERBOS_ATIVIDADE_AMPLIADOS = frozenset({
    "ARMAZENAR", "DISTRIBUIR", "EXPEDIR", "TRANSPORTAR", "FABRICAR",
    "IMPORTAR", "EXPORTAR", "DISPENSAR", "EMBALAR", "REEMBALAR",
    "FRACIONAR", "FRACIONAMENTO", "COMÉRCIO", "COMERCIO",
    "COMÉRCIO VAREJISTA", "COMERCIO VAREJISTA",
    "COMÉRCIO ATACADISTA", "COMERCIO ATACADISTA",
    "PURIFICAR", "SINTETIZAR", "EXTRAIR", "TRANSFORMAR", "MANIPULAR",
    "PRODUZIR", "ENVASAR", "ESTERILIZAR", "ARMAZENAMENTO",
    "DISPENSAÇÃO DE MEDICAMENTOS", "DISPENSACAO DE MEDICAMENTOS",
    "PRESTAÇÃO DE SERVIÇOS FARMACÊUTICOS",
    "PRESTACAO DE SERVICOS FARMACEUTICOS",
})

VERBOS_ATIVIDADE = (
    "ARMAZENAR", "DISTRIBUIR", "EXPEDIR", "TRANSPORTAR",
    "COMÉRCIO", "FABRICAR", "IMPORTAR", "DISPENSAR",
)

RE_CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"

# Formato 1 - nome e CNPJ na mesma linha, separados por barra:
#   "RAZAO SOCIAL LTDA / 00.000.000/0001-00"
RE_EMPRESA = re.compile(rf"(.+?)\s*/\s*({RE_CNPJ})")

# Formato 2 - o do DOU atual: o CNPJ vem rotulado, numa linha propria, e a
# razao social fica na linha imediatamente anterior:
#   "VENTO LESTE EDITORA E PUBLICACOES LTDA"
#   "CNPJ/CPF: 21.098.367/0001-60"
RE_CNPJ_ROTULADO = re.compile(
    rf"\bCNPJ(?:/CPF)?\b[^0-9]{{0,12}}({RE_CNPJ})", re.IGNORECASE
)

# Linhas que sao campo rotulado ("Processo:", "Cidade:", "Valor Aprovado:")
# nunca sao razao social.
RE_CAMPO_ROTULADO = re.compile(r"^[A-Za-zÀ-ÿ /]{3,30}:\s")

# Numeracao do item no inicio da linha ("12.3 - ", "4. ", etc.)
RE_PREFIXO_ITEM = re.compile(r"^[\d\.\-\s]+")

# Blocos de autorizacao sanitaria: "RESOLUCAO-RE No 4.229, DE 27 DE OUTUBRO DE 2026"
RE_RESOLUCAO = re.compile(r"RESOLU[ÇC][ÃA]O[\s\-]*RE\s*N[º°o]?\s*([\d\.]+)", re.I)

# "Art. 1o. Deferir as peticoes de Autorizacao de Funcionamento (AFE) e de ..."
# Sem \b: "Indeferir" contem "deferir", entao a fronteira vem de lookbehind.
RE_DEFERIR = re.compile(r"(?<![A-Za-z\u00c0-\u00ff])Deferir", re.I)
RE_INDEFERIR = re.compile(r"Indeferir", re.I)
RE_ASSUNTO_AFE = re.compile(
    r"Autoriza[\u00e7c][\u00e3a]o de Funcionamento|(?<![A-Z])(?:AFE|AE)(?![A-Z])")

# "25351.171723/2024-19 / 5106734"  -> processo / expediente
RE_PROCESSO = re.compile(r"^(\d{5}\.\d{6}/\d{4}-\d{2})\s*/\s*(\d+)")

# "7110 - AFE - ALTERACAO - FARMACIAS E DROGARIAS - RAZAO SOCIAL / 1140139266"
RE_PETICAO = re.compile(r"^\d+\s*-\s*(AFE|AE)(?![A-Z])\s*-\s*(.+)")

# Linha de atividade: "ARMAZENAR: MEDICAMENTO", "COMERCIO: COSMETICOS / ..."
RE_LINHA_ATIVIDADE = re.compile(r"^([A-ZÀ-Ý][A-ZÀ-Ý Ç]{3,45}):\s*(.*)$")

STATUS_EM_ANALISE = "Em Análise"
STATUS_LIBERADA = "LIBERADA"
STATUS_INDEFERIDO = "INDEFERIDO"

_DEFERIDO = ("DEFERIDO", "CONCESSÃO", "AUTORIZA")


@dataclass
class Resolucao:
    """O bloco a que um registro pertence.

    Na Secao 1 o deferimento nao vem registro a registro: vem no Art. 1o da
    RESOLUCAO-RE, e vale para todo o anexo que a segue.
    """

    numero: str = ""
    status: str = "Em Análise"
    sanitaria: bool = False


@dataclass
class Registro:
    data: str
    pagina: int
    empresa: str
    cnpj: str
    atividades: list[str] = field(default_factory=list)
    status: str = "Em Análise"
    link: str = ""
    resolucao: str = ""
    processo: str = ""
    expediente: str = ""
    peticao: str = ""
    sanitario: bool = False
    # Quando o bloco da empresa comeca numa pagina e termina na seguinte.
    paginas_extras: list[int] = field(default_factory=list)

    def como_linha(self) -> dict:
        return {
            "Data": self.data,
            "Página": self.pagina,
            "Empresa": self.empresa,
            "CNPJ": self.cnpj,
            "Atividades": " | ".join(self.atividades),
            "Status": self.status,
            "Resolução": self.resolucao,
            "Processo": self.processo,
            "Expediente": self.expediente,
            "Petição": self.peticao,
            "Link": self.link,
        }


def classificar(linha: str, status_atual: str) -> str:
    """INDEFERIDO vence, porque 'INDEFERIDO' contem 'DEFERIDO'."""
    maiuscula = linha.upper()
    if STATUS_INDEFERIDO in maiuscula:
        return STATUS_INDEFERIDO
    if any(palavra in maiuscula for palavra in _DEFERIDO):
        return STATUS_LIBERADA
    return status_atual


def _limpar_nome(bruto: str) -> str:
    return RE_PREFIXO_ITEM.sub("", bruto.strip()).strip()


def _serve_como_nome(linha: str) -> bool:
    """A linha anterior ao CNPJ rotulado e a razao social — quando parece uma."""
    limpa = _limpar_nome(linha)
    if len(limpa) <= 4:
        return False
    if RE_CAMPO_ROTULADO.match(limpa):
        return False
    if re.search(RE_CNPJ, limpa):
        return False
    return True


def extrair_da_pagina(
    texto: str,
    pagina: int,
    data: str,
    link: str,
    aberto: Registro | None = None,
    linha_anterior: str = "",
    resolucao: Resolucao | None = None,
) -> tuple[list[Registro], Registro | None, str, Resolucao]:
    """Le uma pagina e devolve (fechados, aberto, ultima_linha, resolucao)."""
    fechados: list[Registro] = []
    atual = aberto
    anterior = linha_anterior
    res = resolucao or Resolucao()

    if atual is not None and atual.pagina != pagina:
        atual.paginas_extras.append(pagina)

    def abrir(nome: str, cnpj: str) -> None:
        nonlocal atual
        nome = _limpar_nome(nome)
        if len(nome) <= 4:
            return
        if atual is not None:
            fechados.append(atual)
        atual = Registro(
            data=data, pagina=pagina, empresa=nome, cnpj=cnpj, link=link,
            status=res.status, resolucao=res.numero, sanitario=res.sanitaria,
        )

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # Nova RESOLUCAO-RE: comeca um bloco, e o que vinha antes se fecha.
        marca = RE_RESOLUCAO.search(linha)
        if marca:
            if atual is not None:
                fechados.append(atual)
                atual = None
            res = Resolucao(numero=marca.group(1))
            anterior = linha
            continue

        # O Art. 1o diz o desfecho e o assunto do bloco inteiro.
        if RE_INDEFERIR.search(linha):
            res.status = STATUS_INDEFERIDO
        elif RE_DEFERIR.search(linha):
            res.status = STATUS_LIBERADA
        if RE_ASSUNTO_AFE.search(linha):
            res.sanitaria = True

        rotulado = RE_CNPJ_ROTULADO.search(linha)
        if rotulado:
            antes = linha[: rotulado.start()].strip(" -–—:")
            nome = antes if _serve_como_nome(antes) else anterior
            if _serve_como_nome(nome):
                abrir(nome, rotulado.group(1))
            anterior = linha
            continue

        casamento = RE_EMPRESA.search(linha)
        if casamento:
            abrir(casamento.group(1), casamento.group(2))
            anterior = linha
            continue

        anterior = linha

        if atual is None:
            continue

        processo = RE_PROCESSO.match(linha)
        if processo:
            atual.processo, atual.expediente = processo.groups()
            continue

        peticao = RE_PETICAO.match(linha)
        if peticao:
            atual.peticao = f"{peticao.group(1)} - {peticao.group(2).strip()}"
            atual.sanitario = True
            continue

        atividade = RE_LINHA_ATIVIDADE.match(linha)
        if atividade and atividade.group(1) in VERBOS_ATIVIDADE_AMPLIADOS:
            atual.atividades.append(linha)
            continue

        maiuscula = linha.upper()
        if any(maiuscula.startswith(verbo) for verbo in VERBOS_ATIVIDADE):
            atual.atividades.append(linha)

        atual.status = classificar(linha, atual.status)

    return fechados, atual, anterior, res


def extrair(paginas, data: str, link_de, somente_sanitarias: bool = False) -> list[Registro]:
    """Percorre as paginas em ordem, costurando registros partidos entre elas.

    `paginas` sao objetos com .pagina, .texto e .ok (ver dou.coleta).
    `link_de` recebe o numero da pagina e devolve o link publico.
    `somente_sanitarias` mantem so o que veio de bloco de autorizacao
    sanitaria (AFE/AE), descartando o resto da Secao 1.
    """
    registros: list[Registro] = []
    aberto: Registro | None = None
    anterior: int | None = None
    ultima_linha = ""
    resolucao = Resolucao()

    for pag in sorted(paginas, key=lambda p: p.pagina):
        # Buraco na sequencia: o registro aberto nao pode atravessar, porque
        # o meio dele se perdeu.
        if aberto is not None and anterior is not None and pag.pagina != anterior + 1:
            registros.append(aberto)
            aberto = None

        if not pag.ok or not pag.texto:
            if aberto is not None:
                registros.append(aberto)
                aberto = None
            anterior = None
            ultima_linha = ""
            continue

        fechados, aberto, ultima_linha, resolucao = extrair_da_pagina(
            pag.texto, pag.pagina, data, link_de(pag.pagina),
            aberto, ultima_linha, resolucao,
        )
        registros.extend(fechados)
        anterior = pag.pagina

    if aberto is not None:
        registros.append(aberto)

    if somente_sanitarias:
        registros = [r for r in registros if r.sanitario]

    registros.sort(key=lambda r: (r.pagina, r.empresa))
    return registros
