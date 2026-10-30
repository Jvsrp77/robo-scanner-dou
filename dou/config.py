"""Configuração da execução, vinda da linha de comando ou do ambiente."""

from __future__ import annotations

import argparse
import datetime
import os
from dataclasses import dataclass
from pathlib import Path

# Seção 1 do DOU.
JORNAL_PADRAO = 515

# 6 em vez das 50 originais. O robô roda agendado de madrugada, então ninguém
# está esperando o resultado — e 50 conexões simultâneas contra um servidor
# público, todo dia, é padrão de abuso.
THREADS_PADRAO = 6
PAUSA_PADRAO = 0.2


@dataclass(frozen=True)
class Config:
    data: datetime.date
    jornal_id: int = JORNAL_PADRAO
    pagina_inicial: int = 1
    pagina_final: int = 400
    threads: int = THREADS_PADRAO
    pausa: float = PAUSA_PADRAO
    saida: Path = Path(".")
    todas: bool = False
    tempo_limite: int = 15

    @property
    def data_br(self) -> str:
        """Formato que a URL do DOU espera."""
        return self.data.strftime("%d/%m/%Y")

    @property
    def arquivo_saida(self) -> Path:
        return self.saida / f"Relatorio_Geral_{self.data.strftime('%d-%m-%Y')}.xlsx"

    def url(self, pagina: int) -> str:
        return (
            "https://pesquisa.in.gov.br/imprensa/servlet/INPDFViewer"
            f"?jornal={self.jornal_id}&pagina={pagina}"
            f"&data={self.data_br}&captchafield=firstAccess"
        )

    def link_publico(self, pagina: int) -> str:
        return self.url(pagina).replace(
            "servlet/INPDFViewer", "jsp/visualiza/index.jsp"
        )


def _data(texto: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError as erro:
        raise argparse.ArgumentTypeError(
            f"data invalida: {texto!r} (use DD/MM/AAAA)"
        ) from erro


def _env_int(nome: str, padrao: int) -> int:
    valor = os.environ.get(nome)
    return int(valor) if valor else padrao


def da_linha_de_comando(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(
        prog="robo_dou",
        description="Extrai autorizacoes publicadas na Secao 1 do DOU.",
    )
    parser.add_argument(
        "--data", type=_data, default=datetime.date.today(),
        help="data da edicao, em DD/MM/AAAA (padrao: hoje)",
    )
    parser.add_argument(
        "--pagina-inicial", type=int, default=1,
    )
    parser.add_argument(
        "--pagina-final", type=int,
        default=_env_int("DOU_PAGINA_FINAL", 400),
        help="ultima pagina a varrer (padrao: 400)",
    )
    parser.add_argument(
        "--threads", type=int, default=_env_int("DOU_THREADS", THREADS_PADRAO),
        help=f"downloads simultaneos (padrao: {THREADS_PADRAO})",
    )
    parser.add_argument(
        "--pausa", type=float, default=PAUSA_PADRAO,
        help=f"segundos entre requisicoes (padrao: {PAUSA_PADRAO})",
    )
    parser.add_argument(
        "--saida", type=Path, default=Path(os.environ.get("DOU_SAIDA", ".")),
        help="pasta onde gravar o relatorio",
    )
    parser.add_argument(
        "--jornal", type=int, default=_env_int("DOU_JORNAL_ID", JORNAL_PADRAO),
    )
    parser.add_argument(
        "--todas", action="store_true",
        help="nao filtrar: extrai todo CNPJ da Secao 1, e nao so as "
             "autorizacoes sanitarias (AFE/AE)",
    )

    args = parser.parse_args(argv)

    return Config(
        data=args.data,
        jornal_id=args.jornal,
        pagina_inicial=args.pagina_inicial,
        pagina_final=args.pagina_final,
        threads=args.threads,
        pausa=args.pausa,
        saida=args.saida,
        todas=args.todas,
    )
