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

# "RAZAO SOCIAL LTDA / 00.000.000/0001-00"
RE_EMPRESA = re.compile(r"(.+?)\s*/\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})")

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


def extrair_da_pagina(
    texto: str,
    pagina: int,
    data: str,
    link: str,
    aberto: Registro | None = None,
) -> tuple[list[Registro], Registro | None]:
    """Le uma pagina.

    `aberto` e o registro que ficou pela metade no fim da pagina anterior: suas
    atividades continuam sendo acumuladas aqui ate aparecer o proximo CNPJ.
    Devolve os registros fechados e o que sobrou em aberto.
    """
    fechados: list[Registro] = []
    atual = aberto

    if atual is not None and atual.pagina != pagina:
        atual.paginas_extras.append(pagina)

    for linha in texto.split("\n"):
        linha = linha.strip()
        if not linha:
            continue

        casamento = RE_EMPRESA.search(linha)
        if casamento:
            nome = _limpar_nome(casamento.group(1))

            # Linha com CNPJ mas sem nome utilizavel nao abre registro;
            # tambem nao deve engolir o registro anterior.
            if len(nome) <= 4:
                continue

            if atual is not None:
                fechados.append(atual)

            atual = Registro(
                data=data,
                pagina=pagina,
                empresa=nome,
                cnpj=casamento.group(2),
                link=link,
            )
            continue

        if atual is None:
            continue

        maiuscula = linha.upper()
        if any(maiuscula.startswith(verbo) for verbo in VERBOS_ATIVIDADE):
            atual.atividades.append(linha)

        atual.status = classificar(linha, atual.status)

    return fechados, atual


def extrair(paginas, data: str, link_de) -> list[Registro]:
    """Percorre as paginas em ordem, costurando registros partidos entre elas.

    `paginas` sao objetos com .pagina, .texto e .ok (ver dou.coleta).
    `link_de` recebe o numero da pagina e devolve o link publico.
    """
    registros: list[Registro] = []
    aberto: Registro | None = None
    anterior: int | None = None

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
            continue

        fechados, aberto = extrair_da_pagina(
            pag.texto, pag.pagina, data, link_de(pag.pagina), aberto
        )
        registros.extend(fechados)
        anterior = pag.pagina

    if aberto is not None:
        registros.append(aberto)

    registros.sort(key=lambda r: (r.pagina, r.empresa))
    return registros
