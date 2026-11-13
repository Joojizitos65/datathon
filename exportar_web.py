"""Exporta as tabelas agregadas para web/dados.js, consumido pelo painel estático em web/.

    python exportar_web.py

O painel web não usa servidor: web/index.html abre direto do disco (duplo clique), por isso
os dados vão como um arquivo .js (window.DADOS) e não como JSON carregado por fetch.
Nesta primeira versão o recorte é a indústria (seções B a F), foco do desafio.
"""
from __future__ import annotations

import json

import pandas as pd

import config as cfg
import referencias as ref

PASTA = cfg.DIR_PROC / "agregados"
SAIDA = cfg.BASE / "web" / "dados.js"
IND = cfg.SETOR_INDUSTRIA


def ler(nome: str) -> pd.DataFrame:
    return pd.read_parquet(PASTA / f"{nome}.parquet")


def registros(df: pd.DataFrame, colunas: dict[str, str], casas: int = 2) -> list[dict]:
    """Seleciona e renomeia colunas; arredonda e troca NaN por None (JSON válido)."""
    out = df[list(colunas)].rename(columns=colunas).round(casas)
    return json.loads(out.to_json(orient="records", force_ascii=False))


def malha_compacta() -> list[dict]:
    """Malha municipal com 3 casas decimais (~100 m), suficiente para o mapa do estado."""
    feicoes = []
    for f in ref.malha_municipios()["features"]:
        g = f["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        aneis = [[[round(x, 3), round(y, 3)] for x, y, *_ in anel] for pol in poligonos for anel in pol]
        feicoes.append({"id": str(f["properties"]["codarea"]), "aneis": aneis})
    return feicoes


def main() -> None:
    meta = json.loads((PASTA / "metadados.json").read_text(encoding="utf-8"))
    estado = ler("estado_setor")
    micro = ler("micro_setor")
    mensal = ler("mensal_micro")
    divisao = ler("estado_divisao")
    mun = ler("municipio_setor")
    dim = ler("dim_municipio")[["municipio_codigo", "codigo_ibge", "microrregiao_nome"]]

    mensal_ind = (mensal[mensal["setor"] == IND].groupby("competencia", as_index=False)
                  [["admissoes", "desligamentos", "saldo"]].sum())
    mun_ind = mun[mun["setor"] == IND].merge(dim, on="municipio_codigo", how="left")
    mun_ind["codigo_ibge"] = mun_ind["codigo_ibge"].astype(str)

    indicadores = {"admissoes": "admissoes", "desligamentos": "desligamentos", "saldo": "saldo",
                   "saldo_por_10mil": "saldo10", "adm_por_10mil": "adm10",
                   "sal_mediana_adm": "sal_adm", "sal_mediana_desl": "sal_desl",
                   "pct_pedido_desl": "pct_pedido", "pct_superior_adm": "pct_superior"}
    dados = {
        "meta": {"gerado_em": meta["gerado_em"], "janela": meta["janela_competencias"],
                 "linhas": meta["linhas_analisadas"], "saldo_estado": meta["saldo_estado"]},
        "estado": registros(estado[estado["setor"] == IND], {**indicadores, "razao_desl_adm": "razao"}, 4)[0],
        "micro": registros(micro[micro["setor"] == IND],
                           {"microrregiao_nome": "nome", **indicadores, "sal_adm_rel": "sal_rel",
                            "cenario": "cenario", "fatores": "fatores"}, 3),
        "mensal": registros(mensal_ind, {"competencia": "competencia", "admissoes": "admissoes",
                                          "desligamentos": "desligamentos", "saldo": "saldo"}),
        "divisoes": registros(divisao, {"divisao": "codigo", "divisao_nome": "nome", "saldo": "saldo",
                                        "admissoes": "admissoes", "sal_mediana_adm": "sal_adm",
                                        "pct_pedido_desl": "pct_pedido"}, 3),
        "municipios": registros(mun_ind, {"codigo_ibge": "id", "municipio_nome": "nome",
                                          "microrregiao_nome": "micro", "saldo": "saldo",
                                          "saldo_por_10mil": "saldo10", "adm_por_10mil": "adm10",
                                          "sal_mediana_adm": "sal_adm", "pct_pedido_desl": "pct_pedido"}, 3),
        "malha": malha_compacta(),
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("window.DADOS = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + ";\n",
                     encoding="utf-8")
    print(f"{SAIDA} ({SAIDA.stat().st_size / 1024:.0f} KB): {len(dados['micro'])} microrregiões, "
          f"{len(dados['municipios'])} municípios, {len(dados['divisoes'])} divisões CNAE")


if __name__ == "__main__":
    main()
