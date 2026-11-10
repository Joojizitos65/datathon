# Datathon 2026 — Raio-X do Mercado de Trabalho Industrial em SC

Pipeline de dados para responder à pergunta central do desafio:

> **Quais regiões e setores industriais de Santa Catarina estão enfrentando apagão
> de mão de obra ou expansão acelerada, e como os indicadores de renda e
> escolaridade explicam esses gargalos?**

## Bases de dados

| Arquivo | Conteúdo | Observações técnicas |
|---|---|---|
| `Novo_Caged_MOV_Limpo.csv` | Microdados do Novo CAGED — SC (3.397.416 linhas) | separador `;`, decimais com `,`, 2 colunas `Unnamed` de índice |
| `Municipios_SC_limpo.csv` | Demografia dos 295 municípios de SC | separador `,`, decimais com `.`, código IBGE de 7 dígitos |
| `Dicionario_de_dados.xlsx` | Metadados / códigos → descrições | base para `src/dicionarios.py` |

### Fatos verificados na base
- UF sempre 42 (Santa Catarina).
- Período concentrado em **2025-09 a 2026-08** (12 meses).
- Saldo: **1.719.449 admissões** vs **1.677.967 desligamentos** (saldo líquido +41.482).
- Seção **C (Indústrias de Transformação)** é a maior: 836.753 registros.
- A base já veio **sem a coluna de exclusão** — os registros `EX` já foram filtrados.
- **Join de município:** o CAGED usa código IBGE de **6 dígitos** (`420890`) e a base
  municipal usa **7 dígitos** (`4200051`). A chave é os 6 primeiros dígitos do código
  de 7 → resultou em **0 registros sem correspondência**.

## Estrutura

```
datathon/
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   └── Guia do Participante.docx
├── src/
│   ├── dicionarios.py        # mapeamentos código → rótulo (seção, CBO, grau, etc.)
│   ├── pipeline_ingestao.py  # Etapa 1: ingestão + limpeza + join
│   └── agregacoes.py         # Etapa 2: indicadores (apagão/expansão, saldo/10k hab)
└── data/
    ├── raw/                  # bases originais (não alterar)
    │   ├── Novo_Caged_MOV_Limpo.csv
    │   ├── Municipios_SC_limpo.csv
    │   └── Dicionario_de_dados.xlsx
    ├── processed/            # parquet gerados pelo pipeline (não versionar)
    │   ├── caged_limpo.parquet
    │   ├── municipios_limpo.parquet
    │   └── caged_municipios.parquet
    └── outputs/              # CSVs agregados (indicadores p/ o dashboard)
        ├── agregado_municipios.csv
        ├── agregado_setores.csv
        ├── agregado_classificacao.csv
        └── agregado_perfil_renda_escolaridade.csv
```

## Como executar

```bash
pip install -r requirements.txt

# Etapa 1 — ingestão, limpeza e join (gera os .parquet em data/)
python src/pipeline_ingestao.py

# Etapa 2 — agregações e indicadores (gera os .csv em data/)
python src/agregacoes.py
```

> No Windows, se os `print` com acento quebrarem o console, rode antes:
> `set PYTHONUTF8=1` (cmd) ou `$env:PYTHONUTF8=1` (PowerShell).

## O que o pipeline entrega

1. **Limpeza**: tipos corrigidos (salário/horas com vírgula → float), colunas de
   índice descartadas, UF validada.
2. **Decodificação**: seção CNAE, grau de instrução, tipo de movimentação, sexo,
   raça/cor, categoria e tamanho do estabelecimento traduzidos para texto.
3. **Colunas derivadas**: `eh_admissao`, `eh_desligamento`, `eh_industria`
   (seções B/C/D/E), `escolaridade_ordinal`, `cod_mun6`.
4. **Join territorial** com população, PIB per capita, IDHM e escolarização.
5. **Indicadores**:
   - saldo, admissões, desligamentos e rotatividade por município e por setor;
   - **saldo por 10.000 habitantes** (normalização pedida no guia);
   - classificação em *Expansão acelerada* / *Risco de apagão* / *Estável*;
   - cruzamento renda × escolaridade por setor.

## Próximas etapas (ainda a fazer)

- **Enriquecimento com IA**: agrupar os 200+ CBOs em macrofamílias via LLM.
- **Dashboard** (Streamlit/Power BI) com mapa de SC, ranking de setores e dispersão
  salário × escolaridade — mínimo de 3 KPIs.
- **Pitch executivo** de 3 minutos com as recomendações.
