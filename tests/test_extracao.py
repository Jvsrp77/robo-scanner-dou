"""Testes da leitura do texto do DOU. Nenhum acessa a rede."""

from dou.coleta import PaginaBaixada
from dou.extracao import (
    Resolucao,
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


def extrair_texto(texto, pagina=1, aberto=None, anterior="", resolucao=None):
    """Descarta o que so os testes de contexto precisam."""
    fechados, aberto, _, _ = extrair_da_pagina(
        texto, pagina, DATA, link(pagina), aberto, anterior, resolucao
    )
    return fechados, aberto


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

# ------------------------------------------------- formato atual do DOU
# O CNPJ vem rotulado, em linha propria, e a razao social fica na anterior.
# Trecho com a estrutura real da Secao 1.

TRECHO_DOU = chr(10).join([
    "AREA: 4 Artes Visuais (Artigo 18 , 1)",
    "2512192 - Exposicao Treelogia - As Arvores e o Tempo",
    "VENTO LESTE EDITORA E PUBLICACOES LTDA",
    "CNPJ/CPF: 21.098.367/0001-60",
    "Processo: 01400038883202547",
    "Cidade: Sao Paulo - SP;",
    "Valor Aprovado: R$ 344.668,50",
])


def test_reconhece_cnpj_rotulado_com_nome_na_linha_anterior():
    _, aberto = extrair_texto(TRECHO_DOU)

    assert aberto is not None
    assert aberto.empresa == "VENTO LESTE EDITORA E PUBLICACOES LTDA"
    assert aberto.cnpj == "21.098.367/0001-60"


def test_campo_rotulado_nao_vira_razao_social():
    texto = chr(10).join([
        "Processo: 01400038883202547",
        "CNPJ/CPF: 21.098.367/0001-60",
    ])
    fechados, aberto = extrair_texto(texto)

    assert fechados == []
    assert aberto is None


def test_cnpj_rotulado_na_mesma_linha_que_o_nome():
    texto = "titulada pela entidade PATRIMONIAL LR LTDA., CNPJ n 03.851.648/0001-60,"
    _, aberto = extrair_texto(texto)

    assert aberto is not None
    assert aberto.cnpj == "03.851.648/0001-60"
    assert "PATRIMONIAL LR LTDA" in aberto.empresa


def test_nome_na_pagina_anterior_ao_cnpj():
    # A razao social fecha a pagina 10; o CNPJ abre a 11.
    pagina_10 = PaginaBaixada(10, texto="INSTITUTO CAVALCANTI HATHERLY")
    pagina_11 = PaginaBaixada(11, texto="CNPJ/CPF: 52.819.309/0001-01")

    registros = extrair([pagina_10, pagina_11], DATA, link)

    assert len(registros) == 1
    assert registros[0].empresa == "INSTITUTO CAVALCANTI HATHERLY"
    assert registros[0].cnpj == "52.819.309/0001-01"


def test_dois_proponentes_seguidos_viram_dois_registros():
    texto = chr(10).join([
        "VENTO LESTE EDITORA E PUBLICACOES LTDA",
        "CNPJ/CPF: 21.098.367/0001-60",
        "Valor Aprovado: R$ 344.668,50",
        "AGENCIA DE DESENVOLVIMENTO E INOVACAO SOCIOCULTURAL - ADECULT",
        "CNPJ/CPF: 30.017.987/0001-18",
    ])
    fechados, aberto = extrair_texto(texto)

    assert len(fechados) == 1
    assert fechados[0].cnpj == "21.098.367/0001-60"
    assert aberto.cnpj == "30.017.987/0001-18"

# ------------------------------------------ autorizacao sanitaria (AFE/AE)
# O deferimento nao vem registro a registro: vem no Art. 1o da RESOLUCAO-RE,
# e vale para todo o anexo que a segue.

BLOCO_AFE = chr(10).join([
    "RESOLUCAO-RE No 4.229, DE 27 DE OUTUBRO DE 2026",
    "Art. 1o. Deferir as peticoes de Autorizacao de Funcionamento (AFE) e de",
    "Autorizacao Especial (AE), conforme anexo.",
    "ANEXO",
    "DOSFARMAS LTDA / 53.701.552/0001-93",
    "25351.171723/2024-19 / 5106734",
    "COMERCIO: ALIMENTOS PERMITIDOS / COSMETICOS",
    "7110 - AFE - ALTERACAO - FARMACIAS E DROGARIAS / 1140139266",
])


def test_deferimento_vem_da_resolucao_e_nao_do_registro():
    _, aberto = extrair_texto(BLOCO_AFE)

    assert aberto is not None
    assert aberto.empresa == "DOSFARMAS LTDA"
    assert aberto.status == STATUS_LIBERADA
    assert aberto.resolucao == "4.229"
    assert aberto.sanitario is True


def test_indeferimento_tambem_vem_da_resolucao():
    texto = BLOCO_AFE.replace("Deferir as peticoes", "Indeferir as peticoes")
    _, aberto = extrair_texto(texto)

    assert aberto.status == STATUS_INDEFERIDO


def test_processo_expediente_e_peticao_sao_capturados():
    _, aberto = extrair_texto(BLOCO_AFE)

    assert aberto.processo == "25351.171723/2024-19"
    assert aberto.expediente == "5106734"
    assert aberto.peticao.startswith("AFE - ALTERACAO")
    assert aberto.atividades == ["COMERCIO: ALIMENTOS PERMITIDOS / COSMETICOS"]


def test_filtro_descarta_o_que_nao_e_autorizacao_sanitaria():
    rouanet = PaginaBaixada(10, texto=chr(10).join([
        "VENTO LESTE EDITORA E PUBLICACOES LTDA",
        "CNPJ/CPF: 21.098.367/0001-60",
    ]))
    sanitaria = PaginaBaixada(11, texto=BLOCO_AFE)

    todas = extrair([rouanet, sanitaria], DATA, link)
    so_afe = extrair([rouanet, sanitaria], DATA, link, somente_sanitarias=True)

    assert len(todas) == 2
    assert len(so_afe) == 1
    assert so_afe[0].empresa == "DOSFARMAS LTDA"


def test_nova_resolucao_fecha_o_registro_anterior():
    texto = BLOCO_AFE + chr(10) + "RESOLUCAO-RE No 4.230, DE 27 DE OUTUBRO DE 2026"
    fechados, aberto = extrair_texto(texto)

    assert len(fechados) == 1
    assert fechados[0].empresa == "DOSFARMAS LTDA"
    assert aberto is None
