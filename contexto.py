"""Carrega data/contexto.json (fontes_datathon/contexto.json) e preenche os números calculados.

O arquivo guarda textos editáveis pela equipe (cards de contexto estadual, casos por
município com notícia e fonte, e recomendações). A equipe edita o texto sem tocar no
código; este módulo só resolve duas coisas a partir das tabelas agregadas:

1. Casos por município: soma o saldo (12 meses, indústria) das subclasses CNAE listadas
   em cada caso, nos municípios listados, usando a tabela `municipio_subclasse`.
2. Recomendações: substitui os termos entre chaves (ex.: `{pct_pedido_ind}`) pelos
   números correspondentes, calculados a partir das tabelas agregadas (indústria B-F,
   12 meses).
"""
from __future__ import annotations

import json

import pandas as pd

import config as cfg


def carregar() -> dict:
    return json.loads(cfg.CONTEXTO_JSON.read_text(encoding="utf-8"))


def nosso_dado_caso(caso: dict, municipio_subclasse: pd.DataFrame, dim_mun: pd.DataFrame) -> dict:
    """Soma o saldo das subclasses do caso nos municípios listados. Devolve saldo e nº de linhas."""
    nomes = dim_mun.set_index("municipio_nome")["municipio_codigo"]
    codigos = [nomes.get(m) for m in caso["municipios"]]
    codigos = [c for c in codigos if c is not None]
    sel = municipio_subclasse[
        municipio_subclasse["municipio_codigo"].isin(codigos)
        & municipio_subclasse["subclasse"].isin(caso["subclasses"])
    ]
    return {
        "saldo": int(sel["saldo"].sum()) if len(sel) else None,
        "admissoes": int(sel["admissoes"].sum()) if len(sel) else None,
        "desligamentos": int(sel["desligamentos"].sum()) if len(sel) else None,
        "encontrado": len(sel) > 0,
    }


def fmt_saldo(v) -> str:
    if v is None:
        return "dado indisponível"
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{v:,}".replace(",", ".")


def _pct_pedido(est_div: pd.DataFrame, divisao: int) -> float | None:
    linha = est_div[est_div["divisao"] == divisao]
    if linha.empty or pd.isna(linha.iloc[0]["pct_pedido_desl"]):
        return None
    return float(linha.iloc[0]["pct_pedido_desl"])


def _saldo_divisao(est_div: pd.DataFrame, divisao: int) -> int | None:
    linha = est_div[est_div["divisao"] == divisao]
    return int(linha.iloc[0]["saldo"]) if not linha.empty else None


def _fmt_pct(v) -> str:
    return "dado indisponível" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def _fmt_moeda(v) -> str:
    return "dado indisponível" if v is None else f"R$ {v:,.0f}".replace(",", ".")


# Divisões CNAE (2 dígitos) usadas nos placeholders das recomendações.
DIVISAO_ALIMENTOS = 10
DIVISAO_VESTUARIO = 14
DIVISAO_MATERIAL_ELETRICO = 27
DIVISAO_CONSTRUCAO_NAVAL = 30  # "outros equipamentos de transporte" (inclui embarcações)
DIVISAO_MANUTENCAO_MAQUINAS = 33
MUNICIPIOS_PLANALTO_NORTE = ["São Bento do Sul", "Rio Negrinho", "Campo Alegre", "Mafra"]


def calcular_placeholders(
    est_setor: pd.DataFrame, est_div: pd.DataFrame, est_escolaridade: pd.DataFrame,
    municipio_setor: pd.DataFrame, dim_mun: pd.DataFrame, setor_industria: str,
) -> dict[str, str]:
    """Números para as recomendações de data/contexto.json (indústria B-F, 12 meses)."""
    ind = est_setor[est_setor["setor"] == setor_industria].iloc[0]
    # Texto da recomendação já diz "ganha X% a menos"; o percentual mostrado é positivo.
    gap_ind = (1 - ind["sal_mediana_adm"] / ind["sal_mediana_desl"]) if ind["sal_mediana_desl"] else None

    escol = est_escolaridade[est_escolaridade["setor"] == setor_industria]
    sal_sup = escol.loc[escol["escolaridade_grupo"] == "Superior completo ou mais", "sal_mediana_adm"]
    sal_med = escol.loc[escol["escolaridade_grupo"] == "Médio completo", "sal_mediana_adm"]

    nomes = dim_mun.set_index("municipio_nome")["municipio_codigo"]
    codigos_planalto = [nomes.get(m) for m in MUNICIPIOS_PLANALTO_NORTE if nomes.get(m) is not None]
    ms_ind = municipio_setor[municipio_setor["setor"] == setor_industria]
    saldo_planalto = int(ms_ind[ms_ind["municipio_codigo"].isin(codigos_planalto)]["saldo"].sum())

    pct_pedido_ind = float(ind["pct_pedido_desl"]) if pd.notna(ind["pct_pedido_desl"]) else None
    return {
        "pct_pedido_ind": _fmt_pct(pct_pedido_ind),
        "pct_pedido_alim": _fmt_pct(_pct_pedido(est_div, DIVISAO_ALIMENTOS)),
        "pct_pedido_vest": _fmt_pct(_pct_pedido(est_div, DIVISAO_VESTUARIO)),
        "gap_ind": _fmt_pct(gap_ind),
        "saldo_planalto": fmt_saldo(saldo_planalto),
        "saldo_alim": fmt_saldo(_saldo_divisao(est_div, DIVISAO_ALIMENTOS)),
        "saldo_eletr": fmt_saldo(_saldo_divisao(est_div, DIVISAO_MATERIAL_ELETRICO)),
        "saldo_naval": fmt_saldo(_saldo_divisao(est_div, DIVISAO_CONSTRUCAO_NAVAL)),
        "saldo_manut": fmt_saldo(_saldo_divisao(est_div, DIVISAO_MANUTENCAO_MAQUINAS)),
        "sal_sup": _fmt_moeda(float(sal_sup.iloc[0]) if len(sal_sup) and pd.notna(sal_sup.iloc[0]) else None),
        "sal_med": _fmt_moeda(float(sal_med.iloc[0]) if len(sal_med) and pd.notna(sal_med.iloc[0]) else None),
    }
