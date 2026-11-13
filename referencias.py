"""Tabelas de referência: cadastro de municípios, território IBGE, CNAE e malha geográfica.

As consultas ao IBGE são salvas em `dados_externos/` e reaproveitadas nas execuções
seguintes, então o pipeline só precisa de internet na primeira vez.
"""
from __future__ import annotations

import gzip
import json
import time
import unicodedata
import urllib.request
from functools import lru_cache

import pandas as pd

import config as cfg

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/42/municipios"
URL_CNAE_DIVISOES = "https://servicodados.ibge.gov.br/api/v2/cnae/divisoes"
URL_MALHA = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/42"
    "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=minima"
)


def _baixar_json(url: str, tentativas: int = 3, espera: float = 2.0):
    """Baixa um JSON do IBGE. O servidor pode responder em gzip, então tratamos isso."""
    ultimo_erro = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "datathon-sc/1.0", "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                corpo = resp.read()
            if corpo[:2] == b"\x1f\x8b":
                corpo = gzip.decompress(corpo)
            return json.loads(corpo.decode("utf-8"))
        except Exception as erro:  # rede, timeout, JSON inválido
            ultimo_erro = erro
            time.sleep(espera * (i + 1))
    raise RuntimeError(
        f"Não foi possível baixar {url}: {ultimo_erro}. "
        f"Sem internet, copie os arquivos de cache para {cfg.DIR_EXTERNOS}."
    )


# --- Dicionário de dados ------------------------------------------------------
@lru_cache(maxsize=1)
def _abas_dicionario() -> dict[str, str]:
    nomes = pd.ExcelFile(cfg.DICIONARIO_XLSX).sheet_names
    return {unicodedata.normalize("NFC", n): n for n in nomes}


def aba_dicionario(nome: str) -> pd.DataFrame:
    """Lê uma aba do dicionário (Código | Descrição), comparando nomes sem depender da normalização Unicode."""
    abas = _abas_dicionario()
    chave = unicodedata.normalize("NFC", nome)
    if chave not in abas:
        raise KeyError(f"Aba '{nome}' não encontrada. Abas: {list(abas)}")
    return pd.read_excel(cfg.DICIONARIO_XLSX, sheet_name=abas[chave], dtype=str)


def nomes_setor() -> dict[str, str]:
    """Seção CNAE -> descrição, mais o agregado 'Indústria'."""
    aba = aba_dicionario("seção")
    nomes = dict(zip(aba.iloc[:, 0].str.strip(), aba.iloc[:, 1].str.strip()))
    nomes[cfg.SETOR_INDUSTRIA] = cfg.NOME_INDUSTRIA
    return nomes


# --- Cadastro de municípios (CSV fornecido) -----------------------------------
_COLUNAS_CADASTRO = {
    "Código": "codigo_ibge",
    "Município": "municipio_nome",
    "Área Territorial": "area_km2",
    "População no último censo": "pop_censo_2022",
    "Densidade demográfica": "densidade_hab_km2",
    "População estimada": "pop_estimada_2026",
    "Escolarização": "escolarizacao_6_14_pct",
    "IDHM": "idhm_2010",
    "Mortalidade infantil": "mortalidade_infantil",
    "Total de receitas": "receitas_brutas_2025",
    "Total de despesas": "despesas_empenhadas_2025",
    "PIB per capita": "pib_per_capita_2023",
}


def cadastro_municipios() -> pd.DataFrame:
    """Lê Municipios_SC_limpo.csv.

    Problemas tratados: (1) a última linha é uma nota de rodapé em HTML; (2) os nomes
    das colunas trazem unidade/ano e tags <span>; (3) "-" significa dado ausente;
    (4) a coluna "Unnamed: 14" está vazia.
    """
    bruto = pd.read_csv(cfg.MUNICIPIOS_CSV, dtype=str, encoding="utf-8")

    renomear = {}
    for coluna in bruto.columns:
        for prefixo, novo in _COLUNAS_CADASTRO.items():
            if coluna.startswith(prefixo):
                renomear[coluna] = novo
                break
    faltando = set(_COLUNAS_CADASTRO.values()) - set(renomear.values())
    if faltando:
        raise ValueError(f"Colunas não encontradas em {cfg.MUNICIPIOS_CSV.name}: {sorted(faltando)}")

    df = bruto.rename(columns=renomear)[list(_COLUNAS_CADASTRO.values())]
    df = df[df["codigo_ibge"].fillna("").str.fullmatch(r"\d{7}")].copy()  # descarta o rodapé

    for coluna in df.columns.difference(["municipio_nome"]):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")  # "-" vira NaN
    df["codigo_ibge"] = df["codigo_ibge"].astype("int64")
    df["municipio_codigo"] = (df["codigo_ibge"] // 10).astype("int64")  # chave de 6 dígitos do CAGED
    return df.reset_index(drop=True)


# --- Território (API IBGE) ----------------------------------------------------
def territorio(forcar: bool = False) -> pd.DataFrame:
    """Município -> microrregião, mesorregião, região imediata e intermediária."""
    arquivo = cfg.DIR_EXTERNOS / "territorio_sc.csv"
    if arquivo.exists() and not forcar:
        return pd.read_csv(arquivo, encoding="utf-8")

    linhas = []
    for m in _baixar_json(URL_MUNICIPIOS):
        micro = m.get("microrregiao") or {}
        meso = micro.get("mesorregiao") or {}
        imediata = m.get("regiao-imediata") or {}
        intermediaria = imediata.get("regiao-intermediaria") or {}
        linhas.append(
            {
                "codigo_ibge": m["id"],
                "municipio_nome": m["nome"],
                "microrregiao_id": micro.get("id"),
                "microrregiao_nome": micro.get("nome"),
                "mesorregiao_id": meso.get("id"),
                "mesorregiao_nome": meso.get("nome"),
                "regiao_imediata_nome": imediata.get("nome"),
                "regiao_intermediaria_nome": intermediaria.get("nome"),
            }
        )
    df = pd.DataFrame(linhas)
    if df["microrregiao_id"].isna().any():
        sem = df.loc[df["microrregiao_id"].isna(), "municipio_nome"].tolist()
        raise ValueError(f"Municípios sem microrregião na API do IBGE: {sem}")
    df["municipio_codigo"] = df["codigo_ibge"] // 10
    cfg.DIR_EXTERNOS.mkdir(parents=True, exist_ok=True)
    df.to_csv(arquivo, index=False, encoding="utf-8")
    return df


def divisoes_cnae(forcar: bool = False) -> pd.DataFrame:
    """Divisões CNAE 2.0 (2 dígitos) com nome e seção."""
    arquivo = cfg.DIR_EXTERNOS / "cnae_divisoes.csv"
    if arquivo.exists() and not forcar:
        return pd.read_csv(arquivo, encoding="utf-8")

    linhas = [
        {
            "divisao": int(d["id"]),
            "divisao_nome": d["descricao"].capitalize(),
            "secao": d["secao"]["id"],
        }
        for d in _baixar_json(URL_CNAE_DIVISOES)
    ]
    df = pd.DataFrame(linhas)
    cfg.DIR_EXTERNOS.mkdir(parents=True, exist_ok=True)
    df.to_csv(arquivo, index=False, encoding="utf-8")
    return df


def _area_assinada(anel: list) -> float:
    """Área assinada do anel (fórmula do cadarço): positiva = anti-horário, negativa = horário."""
    return sum(anel[i][0] * anel[i + 1][1] - anel[i + 1][0] * anel[i][1] for i in range(len(anel) - 1)) / 2


def _orientar_aneis(geo: dict) -> dict:
    """Põe os anéis no sentido que o Plotly espera: externo horário, buracos anti-horário.

    A malha do IBGE vem com o anel externo anti-horário (padrão RFC 7946). O `go.Choropleth` do Plotly
    projeta os polígonos numa esfera e, com o sentido invertido, entende cada município como "o mundo
    inteiro menos o município": o mapa fica um retângulo liso, sem divisas.
    """
    for feature in geo.get("features", []):
        g = feature.get("geometry") or {}
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poligono in poligonos:
            for i, anel in enumerate(poligono):
                horario = _area_assinada(anel) < 0
                if horario != (i == 0):  # externo (i == 0) deve ser horário; buracos, anti-horário
                    anel.reverse()
    return geo


def malha_municipios(forcar: bool = False) -> dict:
    """GeoJSON dos municípios de SC (propriedade `codarea` = código IBGE de 7 dígitos).

    Os anéis são reorientados para o sentido esperado pelo Plotly (ver `_orientar_aneis`).
    """
    arquivo = cfg.DIR_EXTERNOS / "malha_sc_municipios.geojson"
    if arquivo.exists() and not forcar:
        return _orientar_aneis(json.loads(arquivo.read_text(encoding="utf-8")))

    geo = _baixar_json(URL_MALHA)
    cfg.DIR_EXTERNOS.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
    return _orientar_aneis(geo)
