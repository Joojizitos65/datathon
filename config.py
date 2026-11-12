"""Configuração central do projeto (Datathon 2026 - Raio-X do Mercado de Trabalho em SC).

Todas as premissas ajustáveis ficam aqui, para que a equipe possa calibrá-las sem
mexer na lógica do pipeline.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent

# --- Entradas (fornecidas pela organização) ---------------------------------
CAGED_CSV = BASE / "Novo_Caged_MOV_Limpo.csv"
MUNICIPIOS_CSV = BASE / "Municipios_SC_limpo.csv"
DICIONARIO_XLSX = BASE / "Dicionario_de_dados.xlsx"
CONTEXTO_JSON = BASE / "fontes_datathon" / "contexto.json"

# --- Saídas -----------------------------------------------------------------
DIR_EXTERNOS = BASE / "dados_externos"        # cache das APIs do IBGE
DIR_PROC = BASE / "dados_processados"         # base limpa + relatórios
DIR_AGREGADOS = DIR_PROC / "agregados"        # tabelas pequenas usadas pelo dashboard
DIR_LLM = BASE / "llm"                        # lotes de prompt e respostas da IA

# --- Leitura e escopo -------------------------------------------------------
CODIGO_UF_SC = 42
CHUNK_LINHAS = 500_000
JANELA_MESES = 12          # o guia pede os "últimos 12 meses"
JANELA_FIM = None          # AAAAMM; None = última competência presente no arquivo

# --- Tipos de movimentação (aba tipomovimentação do dicionário) --------------
TIPOS_ADMISSAO = {10, 20, 25, 35, 70, 97}
TIPOS_DESLIGAMENTO = {31, 32, 33, 40, 43, 45, 50, 60, 80, 90, 98}
TIPO_PEDIDO_DEMISSAO = 40
TIPOS_TERMINO_CONTRATO = {43, 45}

# --- Setor industrial (CNAE 2.0) --------------------------------------------
# Premissa: "indústria" em sentido amplo, como nas Contas Nacionais do IBGE
# (B extrativas, C transformação, D energia, E água/resíduos, F construção).
SECOES_INDUSTRIA = ("B", "C", "D", "E", "F")
SETOR_INDUSTRIA = "IND"
NOME_INDUSTRIA = "Indústria (B a F)"

# --- Salário ----------------------------------------------------------------
# Nas unidades 1, 2, 4 e 5 a mediana de 'salário' fica entre R$ 2.100 e R$ 3.600
# (valor mensal coerente). Nas unidades 3, 6, 7 e 99 a mediana é < R$ 50 ou zero.
UNIDADES_SALARIO_CONFIAVEIS = {1, 2, 4, 5}
SALARIO_MAXIMO = 50_000

# --- Escolaridade (aba graudeinstrução do dicionário) ------------------------
# código -> (grupo, anos de estudo aproximados). Os anos são uma APROXIMAÇÃO
# usada só para comparar médias entre recortes.
ESCOLARIDADE = {
    1: ("Até fundamental incompleto", 0),
    2: ("Até fundamental incompleto", 3),
    3: ("Até fundamental incompleto", 5),
    4: ("Até fundamental incompleto", 7),
    5: ("Fundamental completo / médio incompleto", 9),
    6: ("Fundamental completo / médio incompleto", 10),
    7: ("Médio completo", 12),
    8: ("Superior incompleto", 14),
    9: ("Superior completo ou mais", 16),
    80: ("Superior completo ou mais", 18),
    10: ("Superior completo ou mais", 18),
    11: ("Superior completo ou mais", 22),
}
ESCOLARIDADE_ORDEM = [
    "Até fundamental incompleto",
    "Fundamental completo / médio incompleto",
    "Médio completo",
    "Superior incompleto",
    "Superior completo ou mais",
]
GRAUS_SUPERIOR_COMPLETO = {9, 10, 11, 80}

FAIXAS_ETARIAS_CORTES = [14, 18, 25, 30, 40, 50, 60, 120]
FAIXAS_ETARIAS_ROTULOS = ["14-17", "18-24", "25-29", "30-39", "40-49", "50-59", "60+"]

# --- Classificação de cenários (heurística de ponto de partida) -------------
MIN_MOV_CELULA = 200       # mínimo de movimentações para classificar uma célula
MIN_PARES_GRUPO = 5        # mínimo de células comparáveis para calcular limiares
LIM_SALARIO_REL = 0.95     # admissão paga < 95% da mediana estadual do mesmo setor
LIM_GAP_ANOS_ESTUDO = 0.5  # admitidos com >= 0.5 ano a mais de estudo que os desligados

# --- IA generativa (agrupamento de CBOs) ------------------------------------
COBERTURA_LLM = 0.95       # CBOs que cobrem 95% das movimentações industriais vão ao LLM
TAMANHO_LOTE_LLM = 120
