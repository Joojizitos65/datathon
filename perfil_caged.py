"""Perfil exploratório (somente leitura) do Novo CAGED e da base de municípios de SC.

Lê o CAGED em blocos (arquivo de ~413 MB) e imprime volumetria, nulos e
distribuição das colunas-chave. Não altera nenhum arquivo.
"""
from collections import Counter
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
CAGED = BASE / "Novo_Caged_MOV_Limpo.csv"
MUN = BASE / "Municipios_SC_limpo.csv"

# Colunas que o dicionário descreve; algumas podem não existir no CSV.
COLS_PERFIL = [
    "competênciamov", "uf", "saldomovimentação", "tipomovimentação",
    "indicadordeforadoprazo",
]

rows = 0
nulls = Counter()
dist = {c: Counter() for c in COLS_PERFIL}
pares = Counter()
munis, cbos = set(), set()
cols = None

for ch in pd.read_csv(
    CAGED, sep=";", dtype=str, chunksize=500_000,
    keep_default_na=False, na_values=[""], encoding="utf-8",
):
    if cols is None:
        cols = list(ch.columns)
        ausentes = [c for c in COLS_PERFIL if c not in cols]
        print(f"COLUNAS ({len(cols)}): {cols}")
        if ausentes:
            print("AUSENTES NO CSV (ignoradas):", ausentes)
    rows += len(ch)
    for c in ch.columns:
        nulls[c] += int(ch[c].isna().sum())
    for c in COLS_PERFIL:
        if c in ch.columns:
            dist[c].update(ch[c].fillna("NA").value_counts().to_dict())
    munis.update(ch["município"].dropna().unique().tolist())
    cbos.update(ch["cbo2002ocupação"].dropna().unique().tolist())
    for (s, t), n in ch[["saldomovimentação", "tipomovimentação"]].fillna("NA").value_counts().items():
        pares[(s, t)] += int(n)

print("\nLINHAS TOTAIS:", rows)
print("\nNULOS POR COLUNA (só as que têm):")
for c in cols:
    if nulls[c]:
        print(f"  {c}: {nulls[c]}")
for c in COLS_PERFIL:
    if dist[c]:
        print(f"\n{c.upper()}:", dict(sorted(dist[c].items(), key=lambda x: str(x[0]))))
print("\nMUNICÍPIOS ÚNICOS (CAGED):", len(munis))
print("CBOs ÚNICOS:", len(cbos))
print("\nPARES (saldo, tipo) -> contagem:")
for k, v in sorted(pares.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
    print("  ", k, v)

mun = pd.read_csv(MUN, encoding="utf-8")
print("\nMUNICÍPIOS_SC:", mun.shape)
print(mun.columns.tolist())
