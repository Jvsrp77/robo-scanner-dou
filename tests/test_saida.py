"""Testes da gravacao do relatorio.

O defeito que estes testes travam: a versao anterior, ao falhar no modo
"anexar", gravava o arquivo do zero e apagava o relatorio do dia.
"""

import pandas as pd
import pytest
from openpyxl import load_workbook

from dou.extracao import Registro
from dou.saida import COLUNAS, gravar


def registro(empresa, pagina=1):
    return Registro(
        data="08/12/2025",
        pagina=pagina,
        empresa=empresa,
        cnpj="11.111.111/0001-11",
        atividades=["ARMAZENAR medicamentos", "DISTRIBUIR correlatos"],
        status="LIBERADA",
        link="https://exemplo/1",
    )


def test_grava_as_sete_colunas(tmp_path):
    destino = tmp_path / "relatorio.xlsx"
    gravar([registro("EMPRESA A LTDA")], destino)

    df = pd.read_excel(destino)
    assert list(df.columns) == COLUNAS
    assert df.loc[0, "Empresa"] == "EMPRESA A LTDA"
    # Atividades viram uma string unica, separadas por barra.
    assert df.loc[0, "Atividades"] == "ARMAZENAR medicamentos | DISTRIBUIR correlatos"


def test_cabecalho_destaca_todas_as_colunas(tmp_path):
    destino = tmp_path / "relatorio.xlsx"
    gravar([registro("EMPRESA A LTDA")], destino)

    ws = load_workbook(destino).active
    # Eram 6 de 7: a coluna Link ficava sem destaque.
    for coluna in range(1, len(COLUNAS) + 1):
        assert ws.cell(row=1, column=coluna).fill.start_color.rgb.endswith("FFFF00")


def test_segunda_gravacao_anexa_sem_perder_a_primeira(tmp_path):
    destino = tmp_path / "relatorio.xlsx"

    gravar([registro("EMPRESA A LTDA")], destino)
    total = gravar([registro("EMPRESA B LTDA", pagina=2)], destino)

    assert total == 2
    df = pd.read_excel(destino)
    assert sorted(df["Empresa"]) == ["EMPRESA A LTDA", "EMPRESA B LTDA"]


def test_falha_na_gravacao_nao_destroi_o_arquivo_existente(tmp_path, monkeypatch):
    destino = tmp_path / "relatorio.xlsx"
    gravar([registro("EMPRESA A LTDA")], destino)
    antes = destino.read_bytes()

    def explodir(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(pd.DataFrame, "to_excel", explodir)

    with pytest.raises(OSError):
        gravar([registro("EMPRESA B LTDA")], destino)

    # O relatorio original continua intacto, e nenhum .tmp ficou para tras.
    assert destino.read_bytes() == antes
    assert list(tmp_path.glob("*.tmp.xlsx")) == []
