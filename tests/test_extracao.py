"""Testes da leitura do texto do DOU. Nenhum acessa a rede."""

from dou.coleta import PaginaBaixada
from dou.extracao import (
    STATUS_EM_ANALISE,
    STATUS_INDEFERIDO,
    STATUS_LIBERADA,
    classificar,
    extrair,
    extrair_da_pagina,
)

DATA = "08/12/2025"


def link(pagina: int) -> str:
    return f"https://exemplo/{pagina}"


def extrair_texto(texto, pagina=1, aberto=None):
    return extrair_da_pagina(texto, pagina, DATA, link(pagina), aberto)


# --------------------------------------------------------------- reconhecimento

def test_reconhece_empresa_e_cnpj():
    texto = "12.3 - DISTRIBUIDORA EXEMPLO LTDA / 12.345.678/0001-90"
    fechados, aberto = extrair_texto(texto)

    assert fechados == []
    assert aberto is not None
    assert aberto.empresa == "DISTRIBUIDORA EXEMPLO LTDA"
    assert aberto.cnpj == "12.345.678/0001-90"
    assert aberto.pagina == 1


def test_acumula_atividades_autorizadas():
    texto = "\n".join([
        "1 - EXEMPLO FARMA LTDA / 11.111.111/0001-11",
        "ARMAZENAR medicamentos",
        "DISTRIBUIR correlatos",
        "linha solta que nao e atividade",
        "TRANSPORTAR insumos",
    ])
    _, aberto = extrair_texto(texto)

    assert aberto.atividades == [
        "ARMAZENAR medicamentos",
        "DISTRIBUIR correlatos",
        "TRANSPORTAR insumos",
    ]


def test_nome_curto_demais_nao_abre_registro():
    texto = "AB / 22.222.222/0001-22"
    fechados, aberto = extrair_texto(texto)

    assert fechados == []
    assert aberto is None


def test_segundo_cnpj_fecha_o_primeiro():
    texto = "\n".join([
        "1 - PRIMEIRA EMPRESA LTDA / 11.111.111/0001-11",
        "ARMAZENAR medicamentos",
        "2 - SEGUNDA EMPRESA LTDA / 22.222.222/0001-22",
    ])
    fechados, aberto = extrair_texto(texto)

    assert len(fechados) == 1
    assert fechados[0].empresa == "PRIMEIRA EMPRESA LTDA"
    assert aberto.empresa == "SEGUNDA EMPRESA LTDA"


# ------------------------------------------------------------------ status

def test_deferido_libera():
    assert classificar("Pedido DEFERIDO em 10/01", STATUS_EM_ANALISE) == STATUS_LIBERADA


def test_indeferido_vence_deferido():
    # "INDEFERIDO" contem "DEFERIDO": a ordem da checagem importa.
    assert classificar("Pedido INDEFERIDO", STATUS_EM_ANALISE) == STATUS_INDEFERIDO
    assert classificar("Pedido INDEFERIDO", STATUS_LIBERADA) == STATUS_INDEFERIDO


def test_sem_palavra_chave_mantem_status():
    assert classificar("texto qualquer", STATUS_EM_ANALISE) == STATUS_EM_ANALISE


# -------------------------------------------------- registro partido entre paginas

def test_registro_partido_entre_paginas_e_costurado():
    pagina_10 = PaginaBaixada(10, texto="\n".join([
        "1 - EMPRESA PARTIDA LTDA / 33.333.333/0001-33",
        "ARMAZENAR medicamentos",
    ]))
    pagina_11 = PaginaBaixada(11, texto="\n".join([
        "DISTRIBUIR correlatos",
        "Pedido DEFERIDO",
    ]))

    registros = extrair([pagina_10, pagina_11], DATA, link)

    assert len(registros) == 1
    r = registros[0]
    assert r.empresa == "EMPRESA PARTIDA LTDA"
    assert r.atividades == ["ARMAZENAR medicamentos", "DISTRIBUIR correlatos"]
    assert r.status == STATUS_LIBERADA
    assert r.pagina == 10
    assert r.paginas_extras == [11]


def test_pagina_que_falhou_nao_costura_o_registro_seguinte():
    pagina_10 = PaginaBaixada(10, texto="1 - EMPRESA A LTDA / 44.444.444/0001-44")
    pagina_11 = PaginaBaixada(11, erro="HTTP 500")
    pagina_12 = PaginaBaixada(12, texto="DISTRIBUIR correlatos")

    registros = extrair([pagina_10, pagina_11, pagina_12], DATA, link)

    # A empresa da pagina 10 e fechada sem as atividades da 12, que nao sao dela.
    assert len(registros) == 1
    assert registros[0].empresa == "EMPRESA A LTDA"
    assert registros[0].atividades == []


def test_paginas_fora_de_ordem_sao_reordenadas():
    paginas = [
        PaginaBaixada(3, texto="1 - TERCEIRA LTDA / 33.333.333/0001-33"),
        PaginaBaixada(1, texto="1 - PRIMEIRA LTDA / 11.111.111/0001-11"),
    ]
    registros = extrair(paginas, DATA, link)

    assert [r.pagina for r in registros] == [1, 3]


def test_pagina_sem_pdf_nao_vira_registro():
    paginas = [PaginaBaixada(1, tem_pdf=False), PaginaBaixada(2, tem_pdf=False)]
    assert extrair(paginas, DATA, link) == []
