"""
agregacoes.py
-------------
Etapa 2 do Datathon: gera as tabelas agregadas e os indicadores que alimentam
o dashboard e respondem à pergunta central:

  "Quais regiões e setores industriais de SC estão enfrentando apagão de mão de
   obra ou expansão acelerada, e como renda e escolaridade explicam os gargalos?"

Lê data/processed/caged_municipios.parquet (saída de pipeline_ingestao.py) e grava
CSVs agregados em data/outputs/agregado_*.csv, prontos para Streamlit/Power BI.

Convenções:
  - saldo = admissões - desligamentos (soma de saldomovimentação).
  - "apagão": combina saldo negativo/baixo com alta rotatividade (turnover).
  - "expansão": saldo fortemente positivo.
  - saldo_por_10k_hab: saldo normalizado pela população (métrica do guia).
"""

from pathlib import Path
import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
PROCESSED = RAIZ / "data" / "processed"
OUTPUTS = RAIZ / "data" / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)


def carregar_industria() -> pl.DataFrame:
    df = pl.read_parquet(PROCESSED / "caged_municipios.parquet")
    return df.filter(pl.col("eh_industria"))


def agregar_por_municipio(ind: pl.DataFrame) -> pl.DataFrame:
    """Saldo, volume, rotatividade e indicadores socioeconômicos por município."""
    agg = ind.group_by("cod_mun6", "municipio_nome").agg(
        pl.col("eh_admissao").sum().alias("admissoes"),
        pl.col("eh_desligamento").sum().alias("desligamentos"),
        pl.col("saldomovimentação").sum().alias("saldo"),
        pl.len().alias("movimentacoes"),
        pl.col("salário").filter(pl.col("eh_admissao")).median().alias("salario_mediano_adm"),
        pl.col("escolaridade_ordinal").mean().alias("escolaridade_media"),
        pl.col("populacao_est_2026").first().alias("populacao"),
        pl.col("pib_per_capita_rs").first().alias("pib_per_capita"),
        pl.col("idhm_2010").first().alias("idhm"),
    )

    agg = agg.with_columns(
        # rotatividade: min(adm, desl) / movimentações -> quanto gira sem crescer
        (
            pl.min_horizontal("admissoes", "desligamentos")
            / pl.col("movimentacoes")
        ).alias("rotatividade"),
        # métrica do guia: saldo por 10.000 habitantes
        (pl.col("saldo") / pl.col("populacao") * 10_000).alias("saldo_por_10k_hab"),
    )

    return agg.sort("saldo", descending=True)


def agregar_por_setor(ind: pl.DataFrame) -> pl.DataFrame:
    """Saldo e perfil por seção industrial (B, C, D, E)."""
    return (
        ind.group_by("seção", "seção_desc")
        .agg(
            pl.col("eh_admissao").sum().alias("admissoes"),
            pl.col("eh_desligamento").sum().alias("desligamentos"),
            pl.col("saldomovimentação").sum().alias("saldo"),
            pl.len().alias("movimentacoes"),
            pl.col("salário").filter(pl.col("eh_admissao")).median().alias("salario_mediano_adm"),
            pl.col("escolaridade_ordinal").mean().alias("escolaridade_media"),
        )
        .sort("saldo", descending=True)
    )


def classificar_apagao_expansao(mun: pl.DataFrame, min_mov: int = 200) -> pl.DataFrame:
    """
    Rotula municípios (com volume mínimo) em Expansão / Apagão / Estável a partir
    do saldo por 10k hab e da rotatividade. Usa quantis para limiares robustos.
    """
    base = mun.filter(pl.col("movimentacoes") >= min_mov)

    q_exp = base.select(pl.col("saldo_por_10k_hab").quantile(0.75)).item()
    q_apg = base.select(pl.col("saldo_por_10k_hab").quantile(0.25)).item()
    q_rot = base.select(pl.col("rotatividade").quantile(0.75)).item()

    return base.with_columns(
        pl.when(pl.col("saldo_por_10k_hab") >= q_exp)
        .then(pl.lit("Expansão acelerada"))
        .when(
            (pl.col("saldo_por_10k_hab") <= q_apg)
            | (pl.col("rotatividade") >= q_rot)
        )
        .then(pl.lit("Risco de apagão / alta rotatividade"))
        .otherwise(pl.lit("Estável"))
        .alias("classificacao")
    ).sort("saldo_por_10k_hab", descending=True)


def perfil_renda_escolaridade(ind: pl.DataFrame) -> pl.DataFrame:
    """Compara salário/escolaridade entre admitidos e desligados por setor."""
    return (
        ind.group_by("seção_desc", "graudeinstrução_desc")
        .agg(
            pl.col("eh_admissao").sum().alias("admissoes"),
            pl.col("eh_desligamento").sum().alias("desligamentos"),
            pl.col("saldomovimentação").sum().alias("saldo"),
            pl.col("salário").median().alias("salario_mediano"),
        )
        .sort("saldo", descending=True)
    )


def main():
    ind = carregar_industria()
    print(f"[AGG] movimentações industriais: {ind.height:,}")

    por_mun = agregar_por_municipio(ind)
    por_setor = agregar_por_setor(ind)
    classif = classificar_apagao_expansao(por_mun)
    perfil = perfil_renda_escolaridade(ind)

    por_mun.write_csv(OUTPUTS / "agregado_municipios.csv")
    por_setor.write_csv(OUTPUTS / "agregado_setores.csv")
    classif.write_csv(OUTPUTS / "agregado_classificacao.csv")
    perfil.write_csv(OUTPUTS / "agregado_perfil_renda_escolaridade.csv")

    print("\n== Top 5 municípios em EXPANSÃO (saldo por 10k hab) ==")
    print(classif.filter(pl.col("classificacao") == "Expansão acelerada")
          .select("municipio_nome", "saldo", "saldo_por_10k_hab", "salario_mediano_adm").head(5))

    print("\n== Top 5 municípios em RISCO DE APAGÃO ==")
    print(classif.filter(pl.col("classificacao").str.contains("apagão"))
          .select("municipio_nome", "saldo", "rotatividade", "salario_mediano_adm").head(5))

    print("\n== Setores industriais por saldo ==")
    print(por_setor.select("seção_desc", "saldo", "salario_mediano_adm", "escolaridade_media"))

    print("\nCSVs agregados gravados em:", OUTPUTS)


if __name__ == "__main__":
    main()
