"""Agrupamento de CBOs em macrofamílias.

Duas camadas:
  1. Regra determinística (`macrofamilia_regra`), baseada nos grupos da CBO 2002.
     Garante que o pipeline rode de ponta a ponta sem IA e serve de base de comparação.
  2. Refinamento por IA generativa, via exportação/importação:
       python cbo.py exportar   -> gera prompts em llm/lotes/lote_XX.md
       (colar cada lote no LLM e salvar o CSV devolvido em llm/respostas/)
       python pipeline.py       -> importa as respostas e sobrescreve a regra

O guia aceita "chamadas de API ou exportação/importação de amostras textuais";
aqui está implementada a segunda opção.
"""
from __future__ import annotations

import io
import sys
import unicodedata

import pandas as pd

import config as cfg
import referencias as ref

MACROFAMILIAS = [
    "Direção e gerência",
    "Engenharia e P&D (nível superior)",
    "Tecnologia da informação",
    "Administrativo, financeiro e jurídico",
    "Comercial, vendas e atendimento",
    "Técnicos industriais e de qualidade",
    "Operação de processos e máquinas industriais",
    "Ofícios industriais qualificados (montagem, costura, solda)",
    "Construção civil e infraestrutura",
    "Manutenção e reparação",
    "Logística, transporte e armazenagem",
    "Serviços gerais e apoio",
    "Agropecuária e extrativismo",
    "Outros especialistas e técnicos",
    "Outros / não classificado",
]

NIVEL_POR_GRANDE_GRUPO = {
    "0": "Outros",
    "1": "Gestão",
    "2": "Superior / especialista",
    "3": "Técnico (nível médio)",
    "4": "Operacional / base",
    "5": "Operacional / base",
    "6": "Operacional / base",
    "7": "Operacional / base",
    "8": "Operacional / base",
    "9": "Operacional / base",
}


def cbo6(codigo) -> str:
    """CBO com 6 dígitos. O dicionário perde o zero à esquerda (ex.: 10105 -> 010105)."""
    return str(int(codigo)).zfill(6)


def nivel_cbo(codigo6: str) -> str:
    return NIVEL_POR_GRANDE_GRUPO.get(codigo6[0], "Outros")


def macrofamilia_regra(c: str) -> str:
    """Macrofamília a partir do código CBO de 6 dígitos (regra por grande grupo/subgrupo)."""
    gg, p2, p3 = c[0], c[:2], c[:3]
    if gg == "1":
        return "Direção e gerência"
    if gg == "2":
        if p3 == "212":
            return "Tecnologia da informação"
        if p2 in ("20", "21"):
            return "Engenharia e P&D (nível superior)"
        if p2 in ("24", "25"):
            return "Administrativo, financeiro e jurídico"
        return "Outros especialistas e técnicos"
    if gg == "3":
        if p3 == "317":
            return "Tecnologia da informação"
        if p2 == "31" or p3 == "391":
            return "Técnicos industriais e de qualidade"
        if p2 == "35":
            return "Administrativo, financeiro e jurídico"
        if p2 == "34":
            return "Logística, transporte e armazenagem"
        return "Outros especialistas e técnicos"
    if gg == "4":
        return "Administrativo, financeiro e jurídico"
    if gg == "5":
        return "Comercial, vendas e atendimento" if p2 == "52" else "Serviços gerais e apoio"
    if gg == "6":
        return "Agropecuária e extrativismo"
    if gg == "7":
        if p3 in ("711", "712"):
            return "Agropecuária e extrativismo"
        if p2 == "71":
            return "Construção civil e infraestrutura"
        if p3 == "784":
            return "Operação de processos e máquinas industriais"
        if p2 == "78":
            return "Logística, transporte e armazenagem"
        return "Ofícios industriais qualificados (montagem, costura, solda)"
    if gg == "8":
        return "Operação de processos e máquinas industriais"
    if gg == "9":
        return "Manutenção e reparação"
    return "Outros / não classificado"


def descricoes() -> pd.Series:
    """CBO (6 dígitos) -> descrição, a partir da aba cbo2002ocupação do dicionário."""
    aba = ref.aba_dicionario("cbo2002ocupação")
    codigos = aba.iloc[:, 0].map(cbo6)
    return pd.Series(aba.iloc[:, 1].str.strip().values, index=codigos.values)


# --- Importação das respostas do LLM ------------------------------------------
def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def carregar_respostas() -> tuple[dict[str, str], list[str]]:
    """Lê llm/respostas/*.csv (colunas cbo, macrofamilia). Devolve (mapa, avisos)."""
    pasta = cfg.DIR_LLM / "respostas"
    oficiais = {_normalizar(m): m for m in MACROFAMILIAS}
    mapa: dict[str, str] = {}
    avisos: list[str] = []
    if not pasta.exists():
        return mapa, avisos

    for arquivo in sorted(pasta.glob("*.csv")):
        linhas = [
            l for l in arquivo.read_text(encoding="utf-8-sig").splitlines()
            if l.strip() and not l.strip().startswith("```")
        ]
        try:
            tabela = pd.read_csv(io.StringIO("\n".join(linhas)), sep=None, engine="python", dtype=str)
            tabela.columns = [_normalizar(c) for c in tabela.columns]
            tabela = tabela[["cbo", "macrofamilia"]].dropna()
        except Exception as erro:
            avisos.append(f"{arquivo.name}: formato inválido ({erro})")
            continue
        for codigo, rotulo in zip(tabela["cbo"], tabela["macrofamilia"]):
            oficial = oficiais.get(_normalizar(rotulo))
            if oficial is None:
                avisos.append(f"{arquivo.name}: macrofamília fora da lista para CBO {codigo}: '{rotulo}'")
                continue
            try:
                mapa[cbo6(codigo)] = oficial
            except ValueError:
                avisos.append(f"{arquivo.name}: CBO inválida '{codigo}'")
    return mapa, avisos


def tabela_macrofamilias(cbos: list[str]) -> pd.DataFrame:
    """Para cada CBO: descrição, nível, macrofamília final e a fonte (IA ou regra)."""
    mapa_ia, avisos = carregar_respostas()
    desc = descricoes()
    linhas = []
    for c in cbos:
        ia = mapa_ia.get(c)
        linhas.append(
            {
                "cbo": c,
                "cbo_descricao": desc.get(c, "(sem descrição no dicionário)"),
                "nivel_cbo": nivel_cbo(c),
                "macrofamilia": ia or macrofamilia_regra(c),
                "fonte_macrofamilia": "IA" if ia else "regra",
            }
        )
    out = pd.DataFrame(linhas)
    out.attrs["avisos"] = avisos
    return out


# --- Exportação de lotes para o LLM -------------------------------------------
PROMPT = """Você é especialista em mercado de trabalho industrial brasileiro e na CBO 2002.

Tarefa: classifique cada ocupação (código CBO) abaixo em UMA das macrofamílias da lista.
Contexto: análise de vagas industriais em Santa Catarina. Use a descrição da ocupação e,
quando houver dúvida, escolha a macrofamília que melhor representa a função na indústria.

Macrofamílias permitidas (use exatamente estes nomes):
{lista}

Regras de saída:
- Responda SOMENTE com CSV, separador vírgula, cabeçalho `cbo,macrofamilia`.
- Uma linha por CBO recebida, sem omitir nenhuma, sem texto antes ou depois.
- Se o nome da macrofamília contiver vírgula, coloque-o entre aspas duplas.

Ocupações (cbo | descrição):
{ocupacoes}
"""


def exportar_lotes() -> None:
    caminho = cfg.DIR_PROC / "cbo_volume.csv"
    if not caminho.exists():
        sys.exit(f"{caminho} não existe. Rode `python pipeline.py` primeiro.")
    vol = pd.read_csv(caminho, dtype={"cbo": str})
    vol = vol[vol["mov_industria"] > 0].sort_values("mov_industria", ascending=False)
    acumulado = vol["mov_industria"].cumsum() / vol["mov_industria"].sum()
    vol = vol[acumulado.shift(fill_value=0) < cfg.COBERTURA_LLM]

    pasta = cfg.DIR_LLM / "lotes"
    pasta.mkdir(parents=True, exist_ok=True)
    (cfg.DIR_LLM / "respostas").mkdir(parents=True, exist_ok=True)
    lista = "\n".join(f"- {m}" for m in MACROFAMILIAS)
    n_lotes = 0
    for i in range(0, len(vol), cfg.TAMANHO_LOTE_LLM):
        parte = vol.iloc[i : i + cfg.TAMANHO_LOTE_LLM]
        ocupacoes = "\n".join(f"{c} | {d}" for c, d in zip(parte["cbo"], parte["cbo_descricao"]))
        n_lotes += 1
        (pasta / f"lote_{n_lotes:02d}.md").write_text(
            PROMPT.format(lista=lista, ocupacoes=ocupacoes), encoding="utf-8"
        )
    print(f"{len(vol)} CBOs (cobrem {cfg.COBERTURA_LLM:.0%} das movimentações industriais) em {n_lotes} lotes: {pasta}")
    print(f"Salve cada resposta do LLM como CSV em: {cfg.DIR_LLM / 'respostas'}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "exportar":
        exportar_lotes()
    else:
        print(__doc__)
