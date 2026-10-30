"""Robo Scanner DOU - ponto de entrada.

Varre a Secao 1 do Diario Oficial da Uniao na data informada, extrai as
empresas autorizadas e grava um relatorio Excel.

    python robo_dou.py                      # edicao de hoje
    python robo_dou.py --data 08/12/2025    # edicao passada
    python robo_dou.py --threads 4 --pagina-final 120

Codigo de saida 1 se alguma pagina falhou: pipeline que falha em silencio e
pior que pipeline que quebra.
"""

from __future__ import annotations

import sys
import time

from dou import coleta, extracao, saida
from dou.config import da_linha_de_comando


def _progresso(feitas: int, total: int) -> None:
    if feitas % 50 == 0 or feitas == total:
        print(f"   ...{feitas}/{total} paginas", flush=True)


def main(argv: list[str] | None = None) -> int:
    cfg = da_linha_de_comando(argv)

    print("=" * 62)
    print(f" ROBO DOU - edicao de {cfg.data_br}")
    print(f" paginas {cfg.pagina_inicial}-{cfg.pagina_final}"
          f" | {cfg.threads} threads | pausa {cfg.pausa}s")
    print(" filtro: " + ("nenhum (toda a Secao 1)" if cfg.todas
                         else "autorizacao sanitaria (AFE/AE)"))
    print("=" * 62)

    inicio = time.time()
    paginas = coleta.baixar_todas(cfg, progresso=_progresso)
    registros = extracao.extrair(
        paginas, cfg.data_br, cfg.link_publico,
        somente_sanitarias=not cfg.todas,
    )

    com_pdf = sum(1 for p in paginas if p.ok)
    sem_pdf = sum(1 for p in paginas if p.erro is None and not p.tem_pdf)
    com_erro = [p for p in paginas if p.erro]
    partidos = sum(1 for r in registros if r.paginas_extras)

    total_no_arquivo = 0
    if registros:
        total_no_arquivo = saida.gravar(registros, cfg.arquivo_saida)

    print()
    print(f"{len(paginas):4d} paginas solicitadas")
    print(f"{com_pdf:4d} com PDF valido")
    print(f"{sem_pdf:4d} sem PDF (fim da secao)")
    print(f"{len(com_erro):4d} com erro de rede ou leitura")
    print(f"{len(registros):4d} registros extraidos"
          + (f" ({partidos} continuavam na pagina seguinte)" if partidos else ""))

    if registros:
        print(f"\nRelatorio: {cfg.arquivo_saida} ({total_no_arquivo} linhas no total)")
    else:
        print("\nNenhuma empresa encontrada nessa edicao.")

    print(f"Concluido em {time.time() - inicio:.1f}s")

    if com_erro:
        print(f"\nATENCAO: {len(com_erro)} paginas falharam. O relatorio esta incompleto.")
        for pagina in com_erro[:10]:
            print(f"  pagina {pagina.pagina}: {pagina.erro}")
        if len(com_erro) > 10:
            print(f"  ... e mais {len(com_erro) - 10}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
