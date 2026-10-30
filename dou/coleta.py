"""Download das paginas do DOU e extracao do texto.

O ponto desta camada e nunca confundir os tres desfechos possiveis:
pagina lida, pagina que nao existe (fim da secao) e pagina que falhou.
O codigo anterior devolvia lista vazia nos tres casos.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:                       # nome atual do PyMuPDF
    import pymupdf
except ImportError:        # versoes anteriores a 1.24.3
    import fitz as pymupdf

from .config import Config

CABECALHO = {"User-Agent": "robo-scanner-dou/2.0 (+https://github.com/Jvsrp77/robo-scanner-dou)"}


@dataclass
class PaginaBaixada:
    """Desfecho de uma pagina. Exatamente um dos tres casos e verdadeiro."""

    pagina: int
    texto: str | None = None
    erro: str | None = None
    tem_pdf: bool = True

    @property
    def ok(self) -> bool:
        return self.erro is None and self.tem_pdf


def criar_sessao(cfg: Config) -> requests.Session:
    sessao = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=cfg.threads,
        pool_maxsize=cfg.threads,
    )
    sessao.mount("https://", adapter)
    sessao.headers.update(CABECALHO)
    return sessao


def baixar_pagina(cfg: Config, sessao: requests.Session, pagina: int) -> PaginaBaixada:
    try:
        resposta = sessao.get(cfg.url(pagina), timeout=cfg.tempo_limite)
    except requests.RequestException as erro:
        return PaginaBaixada(pagina, erro=f"{type(erro).__name__}: {erro}")

    if resposta.status_code != 200:
        return PaginaBaixada(pagina, erro=f"HTTP {resposta.status_code}")

    # Resposta 200 sem PDF significa que a pagina nao existe nessa edicao.
    # Nao e erro: e o fim da secao.
    if b"%PDF" not in resposta.content[:1024]:
        return PaginaBaixada(pagina, tem_pdf=False)

    try:
        with pymupdf.open(stream=resposta.content, filetype="pdf") as doc:
            texto = "\n".join(p.get_text("text") for p in doc)
    except Exception as erro:  # PDF corrompido chega aqui
        return PaginaBaixada(pagina, erro=f"PDF ilegivel: {type(erro).__name__}: {erro}")

    return PaginaBaixada(pagina, texto=texto)


def baixar_todas(cfg: Config, progresso=None) -> list[PaginaBaixada]:
    """Baixa o intervalo configurado e devolve o resultado ordenado por pagina."""
    sessao = criar_sessao(cfg)
    paginas = range(cfg.pagina_inicial, cfg.pagina_final + 1)
    resultados: list[PaginaBaixada] = []

    def tarefa(pagina: int) -> PaginaBaixada:
        if cfg.pausa:
            time.sleep(cfg.pausa)
        return baixar_pagina(cfg, sessao, pagina)

    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.threads) as executor:
        futuros = {executor.submit(tarefa, p): p for p in paginas}

        for futuro in concurrent.futures.as_completed(futuros):
            pagina = futuros[futuro]
            try:
                resultados.append(futuro.result())
            except Exception as erro:
                # Nada deveria chegar aqui, mas se chegar vira erro visivel
                # em vez de pagina silenciosamente vazia.
                resultados.append(
                    PaginaBaixada(pagina, erro=f"falha inesperada: {type(erro).__name__}: {erro}")
                )

            if progresso:
                progresso(len(resultados), len(futuros))

    # as_completed devolve fora de ordem; a extracao depende da ordem do jornal.
    resultados.sort(key=lambda r: r.pagina)
    return resultados
