"""Pipeline do Datathon 2026: ingestão -> validação -> limpeza -> cruzamento -> agregação.

Uso:
    python pipeline.py

Saídas:
    dados_processados/caged_limpo.parquet       base limpa e enriquecida (grande, não vai ao Git)
    dados_processados/cbo_volume.csv            CBOs e volumes (insumo para o LLM)
    dados_processados/agregados/*.parquet       tabelas pequenas lidas pelo dashboard
    dados_processados/agregados/relatorio_qualidade.csv   o que foi removido em cada etapa e por quê
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

import cbo as cbomod
import config as cfg
import referencias as ref

COLUNAS_CAGED = [
    "competênciamov", "uf", "município", "seção", "subclasse", "saldomovimentação",
    "cbo2002ocupação", "graudeinstrução", "idade", "horascontratuais", "sexo",
    "tipomovimentação", "indtrabintermitente", "indtrabparcial", "salário",
    "unidadesaláriocódigo", "indicadordeforadoprazo",
]

# Colunas usadas nas agregações (o resto da base limpa não precisa ser empilhado).
COLUNAS_AGREGACAO = [
    "competencia", "municipio_codigo", "microrregiao_id", "secao", "divisao", "industria",
    "macrofamilia", "nivel_cbo", "sexo_rotulo", "faixa_etaria", "escolaridade_grupo",
    "adm", "desl", "sal_adm", "sal_desl", "anos_adm", "anos_desl", "sup_adm", "sup_desl",
    "pedido_desl", "termino_desl", "idade_adm", "idade_desl", "mulher_adm",
]

COLUNAS_BASE_LIMPA = [
    "competencia", "municipio_codigo", "microrregiao_id", "mesorregiao_id", "secao",
    "subclasse", "divisao", "industria", "cbo", "macrofamilia", "nivel_cbo", "saldo",
    "tipo_mov", "grau", "escolaridade_grupo", "idade", "faixa_etaria", "sexo_rotulo",
    "horas", "intermitente", "parcial", "salario", "unidade_salario", "sal_valido", "fora_prazo",
]


def log(msg: str) -> None:
    print(msg, flush=True)


# =============================================================================
# 1. Ingestão
# =============================================================================
def _limpar_chunk(ch: pd.DataFrame) -> pd.DataFrame:
    def inteiro(coluna, tipo):
        return pd.to_numeric(ch[coluna], errors="coerce").astype(tipo)

    def decimal_br(coluna):
        return pd.to_numeric(ch[coluna].str.replace(",", ".", regex=False), errors="coerce")

    return pd.DataFrame(
        {
            "competencia": inteiro("competênciamov", "Int32"),
            "uf": inteiro("uf", "Int8"),
            "municipio_codigo": inteiro("município", "Int32"),
            "secao": ch["seção"].str.strip(),
            "subclasse": inteiro("subclasse", "Int32"),
            "saldo": inteiro("saldomovimentação", "Int8"),
            "cbo_num": inteiro("cbo2002ocupação", "Int32"),
            "grau": inteiro("graudeinstrução", "Int8"),
            "idade": pd.to_numeric(ch["idade"], errors="coerce").astype("float32"),
            "horas": decimal_br("horascontratuais").astype("float32"),
            "sexo": inteiro("sexo", "Int8"),
            "tipo_mov": inteiro("tipomovimentação", "Int8"),
            "intermitente": inteiro("indtrabintermitente", "Int8"),
            "parcial": inteiro("indtrabparcial", "Int8"),
            "salario": decimal_br("salário"),  # vem como "2018,00"
            "unidade_salario": inteiro("unidadesaláriocódigo", "Int8"),
            "fora_prazo": inteiro("indicadordeforadoprazo", "Int8"),
        }
    )


def ler_caged() -> pd.DataFrame:
    cabecalho = pd.read_csv(cfg.CAGED_CSV, sep=";", nrows=0, encoding="utf-8").columns
    faltando = [c for c in COLUNAS_CAGED if c not in cabecalho]
    if faltando:
        raise ValueError(f"Colunas ausentes em {cfg.CAGED_CSV.name}: {faltando}")

    leitor = pd.read_csv(
        cfg.CAGED_CSV, sep=";", dtype=str, usecols=COLUNAS_CAGED, encoding="utf-8",
        na_values=[""], keep_default_na=False, chunksize=cfg.CHUNK_LINHAS,
    )
    partes, lidas = [], 0
    for ch in leitor:
        lidas += len(ch)
        partes.append(_limpar_chunk(ch))
        log(f"  lidas {lidas:,} linhas")
    df = pd.concat(partes, ignore_index=True)
    df["secao"] = df["secao"].astype("category")
    return df


# =============================================================================
# 2. Validação e filtros
# =============================================================================
def validar_e_filtrar(df: pd.DataFrame, terr: pd.DataFrame):
    rel = [{"etapa": "Linhas lidas", "removidas": 0, "restantes": len(df), "obs": ""}]

    def passo(nome: str, manter, obs: str = "") -> None:
        nonlocal df
        antes = len(df)
        manter = pd.Series(manter, index=df.index).fillna(False).astype(bool)
        df = df[manter]
        rel.append({"etapa": nome, "removidas": antes - len(df), "restantes": len(df), "obs": obs})

    essenciais = ["competencia", "uf", "municipio_codigo", "secao", "subclasse", "saldo", "tipo_mov"]
    passo("Chaves essenciais nulas", df[essenciais].notna().all(axis=1))
    passo("UF diferente de SC", df["uf"] == cfg.CODIGO_UF_SC)
    passo("Saldo diferente de -1 ou +1", df["saldo"].isin([-1, 1]))

    adm_ok = (df["saldo"] == 1) & df["tipo_mov"].isin(list(cfg.TIPOS_ADMISSAO))
    desl_ok = (df["saldo"] == -1) & df["tipo_mov"].isin(list(cfg.TIPOS_DESLIGAMENTO))
    passo("Saldo incoerente com o tipo de movimentação", adm_ok | desl_ok)
    passo("Município fora do cadastro de SC", df["municipio_codigo"].isin(terr["municipio_codigo"]))

    fim = int(cfg.JANELA_FIM or df["competencia"].max())
    inicio_p = pd.Period(str(fim), "M") - (cfg.JANELA_MESES - 1)
    inicio = int(inicio_p.strftime("%Y%m"))
    passo(
        f"Competência fora da janela de {cfg.JANELA_MESES} meses ({inicio}-{fim})",
        df["competencia"].between(inicio, fim),
        "movimentações de meses antigos declaradas com atraso",
    )

    df = df.reset_index(drop=True)
    # Depois de validar, trocamos os tipos "anuláveis" por tipos simples (mais rápidos).
    for coluna, tipo in {
        "competencia": "int32", "uf": "int8", "municipio_codigo": "int32",
        "subclasse": "int32", "saldo": "int8", "tipo_mov": "int8",
    }.items():
        df[coluna] = df[coluna].astype(tipo)
    for coluna, padrao, tipo in [
        ("sexo", 9, "int8"), ("grau", 99, "int8"), ("cbo_num", 0, "int32"),
        ("unidade_salario", 99, "int8"), ("intermitente", 9, "int8"),
        ("parcial", 9, "int8"), ("fora_prazo", 0, "int8"),
    ]:
        df[coluna] = df[coluna].fillna(padrao).astype(tipo)

    # Observações (não removem linhas): só entram nos indicadores de renda/idade quando válidas.
    rel.append({"etapa": "Aviso: idade ausente", "removidas": 0, "restantes": len(df),
                "obs": f"{int(df['idade'].isna().sum()):,} registros ficam fora das médias de idade"})
    rel.append({"etapa": "Aviso: filtro de exclusões (MOV x EX)", "removidas": 0, "restantes": len(df),
                "obs": "NÃO aplicado: o CSV não tem indicadordeexclusão nem arquivo EX foi fornecido"})
    return df, pd.DataFrame(rel), (inicio, fim)


# =============================================================================
# 3. Enriquecimento
# =============================================================================
def enriquecer(df: pd.DataFrame, terr: pd.DataFrame) -> pd.DataFrame:
    chave = terr[["municipio_codigo", "microrregiao_id", "mesorregiao_id"]].astype("int32")
    df = df.merge(chave, on="municipio_codigo", how="left")

    df["divisao"] = (df["subclasse"] // 100_000).astype("int16")  # 2 primeiros dígitos da CNAE
    df["industria"] = df["secao"].isin(cfg.SECOES_INDUSTRIA).to_numpy()

    saldo_adm = (df["saldo"] == 1).to_numpy()
    saldo_desl = ~saldo_adm
    df["adm"] = saldo_adm.astype("int8")
    df["desl"] = saldo_desl.astype("int8")

    # Salário: só vale para renda quando a unidade é confiável e o valor é plausível.
    df["sal_valido"] = (
        (df["salario"] > 0) & (df["salario"] <= cfg.SALARIO_MAXIMO)
        & df["unidade_salario"].isin(list(cfg.UNIDADES_SALARIO_CONFIAVEIS))
    ).to_numpy()
    df["sal_adm"] = df["salario"].where(df["sal_valido"].to_numpy() & saldo_adm)
    df["sal_desl"] = df["salario"].where(df["sal_valido"].to_numpy() & saldo_desl)

    # Escolaridade
    grau = df["grau"].astype("float32")
    grupo = grau.map({k: v[0] for k, v in cfg.ESCOLARIDADE.items()})
    df["escolaridade_grupo"] = pd.Categorical(
        grupo, categories=cfg.ESCOLARIDADE_ORDEM + ["Não informada"], ordered=True
    )
    df["escolaridade_grupo"] = df["escolaridade_grupo"].fillna("Não informada")
    anos = grau.map({k: float(v[1]) for k, v in cfg.ESCOLARIDADE.items()}).astype("float32")
    superior = np.where(
        grau.isin(list(cfg.GRAUS_SUPERIOR_COMPLETO)), 1.0,
        np.where(anos.notna(), 0.0, np.nan),
    ).astype("float32")
    df["anos_adm"] = anos.where(saldo_adm)
    df["anos_desl"] = anos.where(saldo_desl)
    df["sup_adm"] = pd.Series(superior).where(saldo_adm)
    df["sup_desl"] = pd.Series(superior).where(saldo_desl)

    # Perfil
    faixa = pd.cut(df["idade"], bins=cfg.FAIXAS_ETARIAS_CORTES, labels=cfg.FAIXAS_ETARIAS_ROTULOS, right=False)
    df["faixa_etaria"] = faixa.cat.add_categories("Não informada").fillna("Não informada")
    df["sexo_rotulo"] = pd.Categorical(
        df["sexo"].map({1: "Homem", 3: "Mulher"}).fillna("Não identificado")
    )
    df["idade_adm"] = df["idade"].where(saldo_adm)
    df["idade_desl"] = df["idade"].where(saldo_desl)
    df["mulher_adm"] = (df["sexo"] == 3).astype("float32").where(saldo_adm)

    # Rotatividade
    tipo = df["tipo_mov"]
    df["pedido_desl"] = (tipo == cfg.TIPO_PEDIDO_DEMISSAO).astype("float32").where(saldo_desl)
    df["termino_desl"] = tipo.isin(list(cfg.TIPOS_TERMINO_CONTRATO)).astype("float32").where(saldo_desl)
    return df


def aplicar_cbo(df: pd.DataFrame):
    """Cria cbo (6 dígitos), nivel_cbo e macrofamilia. Devolve também a tabela por CBO."""
    unicos = np.sort(df["cbo_num"].unique())
    tab = cbomod.tabela_macrofamilias([cbomod.cbo6(c) for c in unicos])
    df["cbo"] = df["cbo_num"].map({int(c): cbomod.cbo6(c) for c in unicos}).astype("category")
    df["macrofamilia"] = df["cbo_num"].map(dict(zip(unicos.tolist(), tab["macrofamilia"]))).astype("category")
    df["nivel_cbo"] = df["cbo_num"].map(dict(zip(unicos.tolist(), tab["nivel_cbo"]))).astype("category")

    vol_total = df.groupby("cbo_num").size()
    vol_ind = df[df["industria"]].groupby("cbo_num").size()
    tab["mov_total"] = [int(vol_total.get(int(c), 0)) for c in unicos]
    tab["mov_industria"] = [int(vol_ind.get(int(c), 0)) for c in unicos]
    return df, tab


# =============================================================================
# 4. Agregações
# =============================================================================
def agregar(df: pd.DataFrame, chaves: list[str], pops: dict) -> pd.DataFrame:
    t = (
        df.groupby(chaves, observed=True)
        .agg(
            admissoes=("adm", "sum"),
            desligamentos=("desl", "sum"),
            sal_mediana_adm=("sal_adm", "median"),
            sal_mediana_desl=("sal_desl", "median"),
            anos_estudo_adm=("anos_adm", "mean"),
            anos_estudo_desl=("anos_desl", "mean"),
            pct_superior_adm=("sup_adm", "mean"),
            pct_superior_desl=("sup_desl", "mean"),
            pct_pedido_desl=("pedido_desl", "mean"),
            pct_termino_desl=("termino_desl", "mean"),
            idade_media_adm=("idade_adm", "mean"),
            idade_media_desl=("idade_desl", "mean"),
            pct_mulher_adm=("mulher_adm", "mean"),
        )
        .reset_index()
    )
    t["saldo"] = t["admissoes"] - t["desligamentos"]
    t["movimentos"] = t["admissoes"] + t["desligamentos"]
    t["razao_desl_adm"] = t["desligamentos"] / t["admissoes"].replace(0, np.nan)

    if "municipio_codigo" in chaves:
        t["populacao"] = t["municipio_codigo"].map(pops["municipio"])
    elif "microrregiao_id" in chaves:
        t["populacao"] = t["microrregiao_id"].map(pops["micro"])
    else:
        t["populacao"] = pops["estado"]
    t["saldo_por_10mil"] = t["saldo"] / t["populacao"] * 10_000
    t["adm_por_10mil"] = t["admissoes"] / t["populacao"] * 10_000
    t["giro_por_10mil"] = t["movimentos"] / t["populacao"] * 10_000
    return t


def com_relativos(t: pd.DataFrame, estado: pd.DataFrame, chaves_ref: list[str]) -> pd.DataFrame:
    """Compara cada célula regional com a referência estadual do mesmo setor/ocupação."""
    r = estado[chaves_ref + ["sal_mediana_adm"]].rename(columns={"sal_mediana_adm": "sal_mediana_adm_estado"})
    t = t.merge(r, on=chaves_ref, how="left")
    t["sal_adm_rel"] = t["sal_mediana_adm"] / t["sal_mediana_adm_estado"]
    t["gap_anos_estudo"] = t["anos_estudo_adm"] - t["anos_estudo_desl"]
    return t


def classificar(t: pd.DataFrame, grupo: list[str]) -> pd.DataFrame:
    """Rotula cada célula (ex.: microrregião x setor) comparando-a com as demais do mesmo grupo.

    Heurística de PONTO DE PARTIDA, em percentis do próprio grupo (limiares em config.py):
      Expansão acelerada: saldo positivo e saldo por 10 mil hab. no quartil superior.
      Sinal de apagão   : muita contratação por habitante (quartil superior), saldo líquido
                          abaixo da mediana e saída voluntária acima da mediana. Em outras
                          palavras, a região contrata muito e não consegue crescer.
      Retração          : saldo negativo e saldo por 10 mil hab. no quartil inferior.
    """
    t = t.copy()
    base = t[t["movimentos"] >= cfg.MIN_MOV_CELULA]
    g = base.groupby(grupo, observed=True)
    lim = pd.DataFrame(
        {
            "n_pares": g.size(),
            "q75_saldo": g["saldo_por_10mil"].quantile(0.75),
            "q25_saldo": g["saldo_por_10mil"].quantile(0.25),
            "med_saldo": g["saldo_por_10mil"].median(),
            "q75_adm": g["adm_por_10mil"].quantile(0.75),
            "med_pedido": g["pct_pedido_desl"].median(),
            "q75_pedido": g["pct_pedido_desl"].quantile(0.75),
            "q75_termino": g["pct_termino_desl"].quantile(0.75),
        }
    ).reset_index()
    t = t.merge(lim, on=grupo, how="left")

    ok = (t["movimentos"] >= cfg.MIN_MOV_CELULA) & (t["n_pares"] >= cfg.MIN_PARES_GRUPO)
    expansao = ok & (t["saldo"] > 0) & (t["saldo_por_10mil"] >= t["q75_saldo"])
    apagao = (
        ok & (t["adm_por_10mil"] >= t["q75_adm"]) & (t["saldo_por_10mil"] <= t["med_saldo"])
        & (t["pct_pedido_desl"] >= t["med_pedido"])
    )
    retracao = ok & (t["saldo"] < 0) & (t["saldo_por_10mil"] <= t["q25_saldo"])
    t["cenario"] = np.select(
        [~ok, expansao, apagao, retracao],
        ["Volume insuficiente", "Expansão acelerada", "Sinal de apagão", "Retração"],
        default="Estável",
    )

    causas = [
        (t["sal_adm_rel"] < cfg.LIM_SALARIO_REL, "Salário de admissão abaixo da mediana estadual do setor"),
        (t["gap_anos_estudo"] >= cfg.LIM_GAP_ANOS_ESTUDO, "Contratados mais escolarizados que os desligados"),
        (t["pct_pedido_desl"] >= t["q75_pedido"], "Alta saída voluntária (pedido de demissão)"),
        (t["pct_termino_desl"] >= t["q75_termino"], "Alto término de contrato (temporário ou sazonal)"),
    ]
    partes = [np.where(m.fillna(False).to_numpy(), txt, "") for m, txt in causas]
    texto = ["; ".join(x for x in linha if x) for linha in zip(*partes)]
    texto = pd.Series(texto, index=t.index).replace("", "Sem fator dominante nos indicadores")
    t["fatores"] = np.where(t["cenario"].isin(["Estável", "Volume insuficiente"]), "", texto)
    limiares = [c for c in lim.columns if c not in grupo and c != "n_pares"]
    return t.drop(columns=limiares)


def agregar_municipio_subclasse(df: pd.DataFrame, nomes_municipio: dict) -> pd.DataFrame:
    """Saldo por município x subclasse CNAE (só indústria), para os casos de data/contexto.json.

    O cubo por divisão (2 dígitos) esconde histórias como a de material elétrico para
    veículos em Navegantes x Mafra; o "nosso dado" dos cards de contexto precisa da
    subclasse (7 dígitos) e do município isolado.
    """
    ind = df[df["industria"]]
    t = (
        ind.groupby(["municipio_codigo", "subclasse"], observed=True)
        .agg(admissoes=("adm", "sum"), desligamentos=("desl", "sum"))
        .reset_index()
    )
    t["saldo"] = t["admissoes"] - t["desligamentos"]
    t["municipio_nome"] = t["municipio_codigo"].map(nomes_municipio)
    return t


def empilhar_setor(df_ag: pd.DataFrame) -> pd.DataFrame:
    """Cria a coluna `setor`: cada seção CNAE e também o agregado 'IND' (indústria B a F)."""
    cats = list(df_ag["secao"].cat.categories) + [cfg.SETOR_INDUSTRIA]
    base = df_ag.assign(setor=df_ag["secao"].astype(pd.CategoricalDtype(cats)))
    ind = df_ag[df_ag["industria"]]
    ind = ind.assign(setor=pd.Categorical([cfg.SETOR_INDUSTRIA] * len(ind), categories=cats))
    return pd.concat([base, ind], ignore_index=True)


def anexar_nomes(t: pd.DataFrame, nomes: dict) -> pd.DataFrame:
    t = t.copy()
    if "microrregiao_id" in t:
        t["microrregiao_nome"] = t["microrregiao_id"].map(nomes["micro"])
    if "municipio_codigo" in t:
        t["municipio_nome"] = t["municipio_codigo"].map(nomes["municipio"])
    if "divisao" in t:
        t["divisao_nome"] = t["divisao"].map(nomes["divisao"])
    if "setor" in t:
        t["setor_nome"] = t["setor"].astype(str).map(nomes["setor"])
    if "secao" in t:
        t["secao_nome"] = t["secao"].astype(str).map(nomes["setor"])
    return t


def salvar(t: pd.DataFrame, nome: str) -> None:
    t = t.copy()
    for coluna in t.columns:
        if isinstance(t[coluna].dtype, pd.CategoricalDtype):
            t[coluna] = t[coluna].astype(str)
    t.to_parquet(cfg.DIR_AGREGADOS / f"{nome}.parquet", index=False)
    log(f"  {nome}: {len(t):,} linhas")


# =============================================================================
# Execução
# =============================================================================
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = time.time()
    cfg.DIR_AGREGADOS.mkdir(parents=True, exist_ok=True)

    log("1/6 Tabelas de referência")
    cadastro = ref.cadastro_municipios()
    terr = ref.territorio()
    divisoes = ref.divisoes_cnae()
    ref.malha_municipios()
    if set(cadastro["codigo_ibge"]) != set(terr["codigo_ibge"]):
        raise ValueError("O cadastro de municípios e o território do IBGE não têm os mesmos códigos.")
    dim_mun = cadastro.merge(
        terr.drop(columns=["municipio_nome", "municipio_codigo"]), on="codigo_ibge", how="left"
    )
    log(f"  {len(dim_mun)} municípios, {dim_mun['microrregiao_id'].nunique()} microrregiões")

    log("2/6 Leitura do CAGED")
    df = ler_caged()

    log("3/6 Validação e filtros")
    df, relatorio, (ini, fim) = validar_e_filtrar(df, terr)
    relatorio.to_csv(cfg.DIR_AGREGADOS / "relatorio_qualidade.csv", index=False, encoding="utf-8")
    log(relatorio.to_string(index=False))

    log("4/6 Cruzamento e enriquecimento")
    df = enriquecer(df, terr)
    df, tab_cbo = aplicar_cbo(df)
    tab_cbo.to_csv(cfg.DIR_PROC / "cbo_volume.csv", index=False, encoding="utf-8")
    for aviso in tab_cbo.attrs.get("avisos", []):
        log(f"  AVISO LLM: {aviso}")
    n_ia = int((tab_cbo["fonte_macrofamilia"] == "IA").sum())
    log(f"  {len(tab_cbo)} CBOs distintas; {n_ia} classificadas pela IA, {len(tab_cbo) - n_ia} pela regra")
    df[COLUNAS_BASE_LIMPA].to_parquet(cfg.DIR_PROC / "caged_limpo.parquet", index=False)

    log("5/6 Agregações")
    pops = {
        "municipio": dim_mun.set_index("municipio_codigo")["pop_estimada_2026"],
        "micro": dim_mun.groupby("microrregiao_id")["pop_estimada_2026"].sum(),
        "estado": float(dim_mun["pop_estimada_2026"].sum()),
    }
    nomes = {
        "micro": dict(zip(terr["microrregiao_id"], terr["microrregiao_nome"])),
        "municipio": dict(zip(dim_mun["municipio_codigo"], dim_mun["municipio_nome"])),
        "divisao": dict(zip(divisoes["divisao"], divisoes["divisao_nome"])),
        "setor": ref.nomes_setor(),
    }
    df_ag = df[COLUNAS_AGREGACAO]
    st = empilhar_setor(df_ag)
    st_ind = st[st["industria"]]
    ind = df_ag[df_ag["industria"]]

    est_setor = agregar(st, ["setor"], pops)
    micro_setor = classificar(
        com_relativos(agregar(st, ["microrregiao_id", "setor"], pops), est_setor, ["setor"]), ["setor"]
    )
    est_div = agregar(ind, ["secao", "divisao"], pops)
    micro_div = classificar(
        com_relativos(agregar(ind, ["microrregiao_id", "secao", "divisao"], pops), est_div, ["secao", "divisao"]),
        ["divisao"],
    )
    est_macro = agregar(st_ind, ["setor", "macrofamilia"], pops)
    micro_macro = classificar(
        com_relativos(agregar(st_ind, ["microrregiao_id", "setor", "macrofamilia"], pops), est_macro,
                      ["setor", "macrofamilia"]),
        ["setor", "macrofamilia"],
    )
    est_nivel = agregar(st_ind, ["setor", "nivel_cbo"], pops)
    micro_nivel = agregar(st_ind, ["microrregiao_id", "setor", "nivel_cbo"], pops)

    tabelas = {
        "estado_setor": est_setor,
        "micro_setor": micro_setor,
        "municipio_setor": agregar(st, ["municipio_codigo", "setor"], pops),
        "mensal_micro": agregar(st, ["competencia", "microrregiao_id", "setor"], pops),
        "estado_divisao": est_div,
        "micro_divisao": micro_div,
        "estado_macrofamilia": est_macro,
        "micro_macrofamilia": micro_macro,
        "estado_nivel": est_nivel,
        "micro_nivel": micro_nivel,
        "perfil": agregar(st, ["setor", "sexo_rotulo", "faixa_etaria", "escolaridade_grupo"], pops),
        "estado_escolaridade": agregar(st, ["setor", "escolaridade_grupo"], pops),
    }

    municipio_subclasse = agregar_municipio_subclasse(
        df, dict(zip(dim_mun["municipio_codigo"], dim_mun["municipio_nome"]))
    )

    log("6/6 Gravação")
    for nome, t in tabelas.items():
        salvar(anexar_nomes(t, nomes), nome)
    salvar(dim_mun, "dim_municipio")
    salvar(tab_cbo, "dim_cbo")
    salvar(municipio_subclasse, "municipio_subclasse")

    ind_estado = est_setor[est_setor["setor"] == cfg.SETOR_INDUSTRIA].iloc[0]
    meta = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "janela_competencias": [ini, fim],
        "linhas_analisadas": int(len(df)),
        "linhas_lidas": int(relatorio.loc[0, "restantes"]),
        "populacao_estado": pops["estado"],
        "saldo_estado": int(est_setor.loc[est_setor["setor"].astype(str) != cfg.SETOR_INDUSTRIA, "saldo"].sum()),
        "saldo_industria": int(ind_estado["saldo"]),
        "secoes_industria": list(cfg.SECOES_INDUSTRIA),
        "parametros": {
            "min_mov_celula": cfg.MIN_MOV_CELULA,
            "lim_salario_rel": cfg.LIM_SALARIO_REL,
            "lim_gap_anos_estudo": cfg.LIM_GAP_ANOS_ESTUDO,
            "unidades_salario_confiaveis": sorted(cfg.UNIDADES_SALARIO_CONFIAVEIS),
            "salario_maximo": cfg.SALARIO_MAXIMO,
        },
    }
    (cfg.DIR_AGREGADOS / "metadados.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log("\nResumo (indústria B a F, últimos 12 meses):")
    log(f"  saldo líquido: {int(ind_estado['saldo']):+,}  | admissões: {int(ind_estado['admissoes']):,}  | desligamentos: {int(ind_estado['desligamentos']):,}")
    log(f"  salário mediano de admissão: R$ {ind_estado['sal_mediana_adm']:,.2f}")
    cont = micro_setor[micro_setor["setor"].astype(str) == cfg.SETOR_INDUSTRIA]["cenario"].value_counts()
    log(f"  cenários por microrregião (indústria): {cont.to_dict()}")
    log(f"\nConcluído em {time.time() - inicio:,.0f}s")


if __name__ == "__main__":
    main()
