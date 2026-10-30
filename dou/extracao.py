"""Leitura do texto do DOU.

Esta camada nao faz rede nem disco: recebe texto e devolve registros.
E o que permite testa-la com trechos salvos, sem depender do DOU estar no ar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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

STATUS_EM_ANALISE = "Em Análise"
STATUS_LIBERADA = "LIBERADA"
STATUS_INDEFERIDO = "INDEFERIDO"

_DEFERIDO = ("DEFERIDO", "CONCESSÃO", "AUTORIZA")


@dataclass
class Registro:
    data: str
    pagina: int
    empresa: str
    cnpj: str
    atividades: list[str] = field(default_factory=list)
    status: str = STATUS_EM_ANALISE
    link: str = ""
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
) -> tuple[list[Registro], Registro | None, str]:
    """Le uma pagina.

    `aberto` e o registro que ficou pela metade no fim da pagina anterior: suas
    atividades continuam sendo acumuladas aqui ate aparecer o proximo CNPJ.
    `linha_anterior` e a ultima linha util da pagina anterior, necessaria
    quando o CNPJ rotulado cai na primeira linha desta.

    Devolve os registros fechados, o que sobrou em aberto e a ultima linha.
    """
    fechados: list[Registro] = []
    atual = aberto
    anterior = linha_anterior

    if atual is not None and atual.pagina != pagina:
        atual.paginas_extras.append(pagina)

    def abrir(nome: str, cnpj: str) -> Registro | None:
        nonlocal atual
        nome = _limpar_nome(nome)
        if len(nome) <= 4:
            return None
        if atual is not None:
            fechados.append(atual)
        atual = Registro(data=data, pagina=pagina, empresa=nome, cnpj=cnpj, link=link)
        return atual

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # Formato 2 primeiro: e o do DOU atual, e a linha "CNPJ/CPF: X"
        # tambem casaria com o formato 1 por causa da barra do CNPJ.
        rotulado = RE_CNPJ_ROTULADO.search(linha)
        if rotulado:
            antes_do_rotulo = linha[: rotulado.start()].strip(" -–—:")
            nome = antes_do_rotulo if _serve_como_nome(antes_do_rotulo) else anterior
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

        maiuscula = linha.upper()
        if any(maiuscula.startswith(verbo) for verbo in VERBOS_ATIVIDADE):
            atual.atividades.append(linha)

        atual.status = classificar(linha, atual.status)

    return fechados, atual, anterior


def extrair(paginas, data: str, link_de) -> list[Registro]:
    """Percorre as paginas em ordem, costurando registros partidos entre elas.

    `paginas` sao objetos com .pagina, .texto e .ok (ver dou.coleta).
    `link_de` recebe o numero da pagina e devolve o link publico.
    """
    registros: list[Registro] = []
    aberto: Registro | None = None
    anterior: int | None = None
    ultima_linha = ""

    for pag in sorted(paginas, key=lambda p: p.pagina):
        # Buraco na sequencia (pagina que falhou ou nao existe): o registro
        # aberto nao pode atravessar, porque o meio dele se perdeu.
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

        fechados, aberto, ultima_linha = extrair_da_pagina(
            pag.texto, pag.pagina, data, link_de(pag.pagina), aberto, ultima_linha
        )
        registros.extend(fechados)
        anterior = pag.pagina

    if aberto is not None:
        registros.append(aberto)

    registros.sort(key=lambda r: (r.pagina, r.empresa))
    return registros
