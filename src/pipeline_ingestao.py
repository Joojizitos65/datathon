"""
pipeline_ingestao.py
--------------------
Etapa 1 do Datathon: Ingestão, limpeza e junção das bases.

Entradas (data/raw/):
  - Novo_Caged_MOV_Limpo.csv   (microdados do Novo CAGED - SC, ~3,4M linhas, ';')
  - Municipios_SC_limpo.csv    (demografia dos municípios de SC, ',')

Saídas (data/processed/):
  - caged_limpo.parquet        base CAGED tratada + decodificada
  - municipios_limpo.parquet   base municipal tratada
  - caged_municipios.parquet   join das duas (grão: registro de movimentação)

Decisões de leitura (verificadas na base real):
  - Separador do CAGED é ';' e os decimais usam ',' (salário "2018,00").
  - As colunas 'Unnamed: 0.1' e 'Unnamed: 0' são índices residuais -> descartadas.
  - A UF é sempre 42 (SC). O arquivo já veio sem a coluna de exclusão (EX já aplicado).
  - O código de município do CAGED tem 6 dígitos (420890); o da base municipal tem
    7 (4200051). Os 6 primeiros dígitos do IBGE-7 == IBGE-6 -> chave de join.
"""

from pathlib import Path
import polars as pl

import dicionarios as dic

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

CAGED_CSV = RAW / "Novo_Caged_MOV_Limpo.csv"
MUN_CSV = RAW / "Municipios_SC_limpo.csv"


def _mapa_expr(coluna: str, mapa: dict, sufixo: str = "_desc") -> pl.Expr:
    """Cria uma expressão que traduz códigos em rótulos via replace_strict."""
    return (
        pl.col(coluna)
        .cast(pl.Utf8)
        .replace_strict(mapa, default="Desconhecido")
        .alias(coluna + sufixo)
    )


def carregar_caged() -> pl.DataFrame:
    """Lê o CAGED, trata tipos, decodifica categorias e deriva colunas de análise."""
    print(f"[CAGED] lendo {CAGED_CSV.name} ...")

    # Lê tudo como string primeiro (infer_schema_length=0) para controlar a
    # conversão de decimais com vírgula manualmente e evitar surpresas de tipo.
    lf = pl.scan_csv(
        CAGED_CSV,
        separator=";",
        infer_schema_length=0,
        encoding="utf8",
    )

    cols = lf.collect_schema().names()
    dropar = [c for c in cols if c.startswith("Unnamed")]

    lf = lf.drop(dropar)

    # Converte numéricos. salário/valorsaláriofixo/horascontratuais usam vírgula.
    def num_virgula(c):
        return (
            pl.col(c).str.replace_all(r"\.", "")  # remove separador de milhar se houver
            .str.replace(",", ".")
            .cast(pl.Float64, strict=False)
            .alias(c)
        )

    lf = lf.with_columns(
        num_virgula("salário"),
        num_virgula("valorsaláriofixo"),
        num_virgula("horascontratuais"),
        pl.col("saldomovimentação").cast(pl.Int8, strict=False),
        pl.col("idade").cast(pl.Float64, strict=False).cast(pl.Int16, strict=False),
    )

    # Decodifica os principais campos categóricos.
    lf = lf.with_columns(
        _mapa_expr("seção", dic.SECAO),
        _mapa_expr("graudeinstrução", dic.GRAU_INSTRUCAO),
        _mapa_expr("tipomovimentação", dic.TIPO_MOVIMENTACAO),
        _mapa_expr("sexo", dic.SEXO),
        _mapa_expr("raçacor", dic.RACA_COR),
        _mapa_expr("categoria", dic.CATEGORIA),
        _mapa_expr("tamestabjan", dic.TAM_ESTAB),
    )

    # Colunas derivadas úteis para a análise.
    lf = lf.with_columns(
        # flags de admissão/desligamento a partir do saldo (+1 / -1)
        (pl.col("saldomovimentação") == 1).alias("eh_admissao"),
        (pl.col("saldomovimentação") == -1).alias("eh_desligamento"),
        # indústria = seções B, C, D, E
        pl.col("seção").is_in(dic.SECOES_INDUSTRIAIS).alias("eh_industria"),
        # ordem ordinal de escolaridade (para médias/rankings)
        pl.col("graudeinstrução")
        .cast(pl.Utf8)
        .replace_strict(
            {k: v for k, v in dic.GRAU_INSTRUCAO_ORDEM.items() if v is not None},
            default=None,
        )
        .alias("escolaridade_ordinal"),
        # chave de join: código IBGE de 6 dígitos (como vem no CAGED)
        pl.col("município").cast(pl.Utf8).str.strip_chars().alias("cod_mun6"),
    )

    df = lf.collect()
    print(f"[CAGED] {df.height:,} linhas x {df.width} colunas")
    return df


def carregar_municipios() -> pl.DataFrame:
    """Lê a base municipal, renomeia colunas longas e cria a chave de 6 dígitos."""
    print(f"[MUN] lendo {MUN_CSV.name} ...")

    renome = {
        "Município [-]": "municipio_nome",
        "Código [-]": "cod_mun7",
        "Gentílico [-]": "gentilico",
        "Prefeito [2025]": "prefeito",
        "Área Territorial - km² [2025]": "area_km2",
        "População no último censo - pessoas [2022]": "populacao_2022",
        "Densidade demográfica - hab/km² [2022]": "densidade_hab_km2",
        "População estimada - pessoas [2026]": "populacao_est_2026",
        "Escolarização <span>6 a 14 anos</span> - % [2022]": "escolarizacao_6a14_pct",
        "IDHM <span>Índice de desenvolvimento humano municipal</span> [2010]": "idhm_2010",
        "Mortalidade infantil - óbitos por mil nascidos vivos [2025]": "mortalidade_infantil",
        "Total de receitas brutas realizadas - R$ [2025]": "receitas_brutas_rs",
        "Total de despesas brutas empenhadas - R$ [2025]": "despesas_brutas_rs",
        "PIB per capita - R$ [2023]": "pib_per_capita_rs",
    }

    df = pl.read_csv(MUN_CSV, separator=",", infer_schema_length=0)

    # Descarta eventual coluna final vazia (vírgula sobrando no header).
    df = df.select([c for c in df.columns if c in renome])
    df = df.rename(renome)

    numericas = [
        "area_km2", "populacao_2022", "densidade_hab_km2", "populacao_est_2026",
        "escolarizacao_6a14_pct", "idhm_2010", "mortalidade_infantil",
        "receitas_brutas_rs", "despesas_brutas_rs", "pib_per_capita_rs",
    ]
    df = df.with_columns(
        [
            # '-' e vazios viram nulo; decimais usam '.'
            pl.col(c).replace("-", None).cast(pl.Float64, strict=False).alias(c)
            for c in numericas
        ]
    )

    # Chave de join: 6 primeiros dígitos do código IBGE de 7.
    df = df.with_columns(
        pl.col("cod_mun7").cast(pl.Utf8).str.strip_chars().str.slice(0, 6).alias("cod_mun6")
    )

    print(f"[MUN] {df.height:,} municípios x {df.width} colunas")
    return df


def juntar(caged: pl.DataFrame, mun: pl.DataFrame) -> pl.DataFrame:
    """Join do CAGED com a demografia municipal pela chave de 6 dígitos."""
    print("[JOIN] cruzando CAGED x municípios por cod_mun6 ...")
    cols_mun = [
        "cod_mun6", "municipio_nome", "populacao_2022", "populacao_est_2026",
        "densidade_hab_km2", "idhm_2010", "escolarizacao_6a14_pct",
        "pib_per_capita_rs", "area_km2",
    ]
    out = caged.join(mun.select(cols_mun), on="cod_mun6", how="left")

    sem_match = out.filter(pl.col("municipio_nome").is_null()).height
    print(f"[JOIN] registros sem município correspondente: {sem_match:,}")
    return out


def main():
    caged = carregar_caged()
    mun = carregar_municipios()
    joined = juntar(caged, mun)

    print("[SAÍDA] gravando parquet em data/processed/ ...")
    caged.write_parquet(PROCESSED / "caged_limpo.parquet")
    mun.write_parquet(PROCESSED / "municipios_limpo.parquet")
    joined.write_parquet(PROCESSED / "caged_municipios.parquet")

    # Resumo rápido de sanidade.
    ind = joined.filter(pl.col("eh_industria"))
    print("\n===== RESUMO =====")
    print(f"Total de movimentações.............: {joined.height:,}")
    print(f"  admissões........................: {joined['eh_admissao'].sum():,}")
    print(f"  desligamentos....................: {joined['eh_desligamento'].sum():,}")
    print(f"  saldo líquido....................: {int(joined['saldomovimentação'].sum()):,}")
    print(f"Movimentações industriais (B,C,D,E): {ind.height:,}")
    print(f"  saldo líquido industrial.........: {int(ind['saldomovimentação'].sum()):,}")
    print("Arquivos gravados em:", PROCESSED)


if __name__ == "__main__":
    main()
