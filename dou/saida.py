"""Gravacao do relatorio em Excel.

A versao anterior tinha um `except` nu em volta do modo "anexar": quando ele
falhava — arquivo aberto no Excel, planilha travada, openpyxl diferente — o
tratamento gravava o arquivo do zero e apagava o relatorio do dia inteiro,
sem aviso. Aqui a gravacao e feita num arquivo temporario e so substitui o
destino quando terminou; qualquer falha propaga em vez de destruir dado.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

COLUNAS = ["Data", "Página", "Empresa", "CNPJ", "Atividades", "Status", "Link"]

_AMARELO = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")


def _destacar_cabecalho(caminho: Path) -> None:
    wb = load_workbook(caminho)
    ws = wb.active
    for coluna in range(1, len(COLUNAS) + 1):   # 7 colunas, nao 6: o Link ficava de fora
        celula = ws.cell(row=1, column=coluna)
        celula.fill = _AMARELO
        celula.font = Font(bold=True)
    ws.freeze_panes = "A2"
    wb.save(caminho)


def gravar(registros, destino: Path) -> int:
    """Grava os registros, anexando se o arquivo do dia ja existir.

    Devolve o total de linhas no arquivo depois da gravacao.
    """
    novo = pd.DataFrame([r.como_linha() for r in registros], columns=COLUNAS)

    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists():
        # Se a leitura falhar, falha aqui — antes de tocar no arquivo bom.
        existente = pd.read_excel(destino)
        combinado = pd.concat([existente, novo], ignore_index=True)
    else:
        combinado = novo

    # O temporario precisa manter a extensao .xlsx: o openpyxl recusa abrir
    # arquivo terminado em .tmp, e o destaque do cabecalho acontece nele.
    temporario = destino.with_name(f".{destino.stem}.tmp{destino.suffix}")
    try:
        combinado.to_excel(temporario, index=False)
        _destacar_cabecalho(temporario)
        os.replace(temporario, destino)   # troca atomica no mesmo volume
    finally:
        if temporario.exists():
            temporario.unlink()

    return len(combinado)
