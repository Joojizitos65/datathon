# Datathon 2026 - Raio-X do Mercado de Trabalho e Vagas Industriais em SC

Base de código para responder à pergunta central do desafio: **quais regiões e setores industriais de
SC enfrentam apagão de mão de obra ou expansão acelerada, e como renda e escolaridade explicam isso?**

## Como rodar

```powershell
pip install -r requirements.txt
python pipeline.py            # ~40 s: lê o CAGED, valida, cruza, agrega e grava tabelas
streamlit run dashboard.py    # abre o painel
```

Os três arquivos da organização (`Novo_Caged_MOV_Limpo.csv`, `Municipios_SC_limpo.csv`,
`Dicionario_de_dados.xlsx`) ficam na raiz do projeto. Na primeira execução o pipeline consulta a API de
localidades do IBGE e guarda o resultado em `dados_externos/`; depois disso não precisa de internet.

## Estrutura

| Arquivo | Função |
|---|---|
| `config.py` | Todas as premissas e limiares ajustáveis (janela, setor industrial, salário, classificação) |
| `referencias.py` | Cadastro de municípios, microrregiões e divisões CNAE (IBGE), dicionário de dados |
| `pipeline.py` | Ingestão, validação, limpeza, cruzamento, indicadores e classificação de cenários |
| `cbo.py` | Macrofamílias de CBO: regra base + exportação/importação para LLM |
| `dashboard.py` | Painel Streamlit (8 abas, mapa, barras, dispersão, mapa de calor) |
| `contexto.py` | Carrega `fontes_datathon/contexto.json` e calcula os números das recomendações e dos casos por município |
| `perfil_caged.py` | Perfil exploratório somente leitura dos dados brutos |

Saídas: `dados_processados/agregados/` (tabelas pequenas, versionadas) e `dados_processados/caged_limpo.parquet`
(base completa limpa, ignorada pelo Git).

## O que o pipeline faz com os dados

1. **Ingestão**: lê o CSV em blocos (separador `;`, decimal com vírgula) e ignora as colunas `Unnamed`.
2. **Validação** (`dados_processados/agregados/relatorio_qualidade.csv`): chaves nulas, UF, saldo, coerência
   saldo x tipo de movimentação, município fora do cadastro e janela de 12 meses.
3. **Cruzamento**: CAGED (município de 6 dígitos) com o cadastro (7 dígitos, usando os 6 primeiros) e com a
   microrregião do IBGE. Normaliza por **saldo por 10 mil habitantes** (população estimada 2026).
4. **Indicadores** por microrregião x setor, divisão CNAE e macrofamília de CBO: saldo, admissões por
   habitante, salário mediano de admissão e de desligamento, escolaridade, pedido de demissão e término de contrato.
5. **Cenários**: "Expansão acelerada", "Sinal de apagão" e "Retração", comparando cada microrregião com as
   demais no mesmo setor (regra em `pipeline.classificar`, limiares em `config.py`).

## Problemas encontrados nos dados (e como foram tratados)

- `indicadordeexclusão` e `competênciaexc` existem no dicionário, mas **não estão no CSV**. O filtro MOV x EX
  que o guia menciona **não pôde ser aplicado**. Vale confirmar com a organização se o arquivo já veio filtrado.
- 6.128 linhas são de competências antigas (2024-09 a 2025-08) declaradas com atraso. Ficam fora da janela de 12 meses.
- `Municipios_SC_limpo.csv` tem uma **nota de rodapé em HTML** como última linha e uma coluna vazia. Foram descartadas.
- Mortalidade infantil está ausente em 123 dos 295 municípios, e IDHM em 2. Os campos não são usados nos indicadores.
- Salário: nas unidades "semana", "tarefa", "variável" e "não identificado" o valor não é mensal ou vem zerado.
  Esses registros entram nos saldos e ficam fora das medianas de renda.
- Não há região menor que "Sul" no CAGED. As microrregiões vêm da API do IBGE.

## Etapa de IA (agrupamento de CBOs)

O guia pede LLM para agrupar as CBOs em macrofamílias. O fluxo é por exportação e importação:

```powershell
python cbo.py exportar        # gera llm/lotes/lote_01..03.md (354 CBOs = 95% das movimentações industriais)
# cole cada lote no LLM e salve a resposta CSV em llm/respostas/ (cabeçalho: cbo,macrofamilia)
python pipeline.py            # importa as respostas; CBOs fora delas ficam com a regra
```

Rótulos fora da lista são rejeitados com aviso. **Ainda nenhuma resposta de LLM foi importada**: hoje todas as
2.206 CBOs usam a regra por grupo da CBO.

## Mapa sem depender de internet

`px.choropleth_map` baixa o fundo do mapa (tiles) de um servidor online; sem rede, o mapa
fica em branco. O painel usa `go.Choropleth`, que só depende de:

- `dados_externos/malha_sc_municipios.geojson`: a malha dos 295 municípios de SC (cache da
  API do IBGE, criado na primeira execução do pipeline). Mantida em vez do
  `fontes_datathon/sc_municipios.geojson` fornecido porque este último tem só 293 polígonos
  (sem Pescaria Brava e Balneário Rincão).
- `static/world_110m.json`: o TopoJSON base que o Plotly normalmente baixa de `cdn.plot.ly`.
  Está versionado em `static/` e `.streamlit/config.toml` liga `enableStaticServing = true`
  para o Streamlit servi-lo localmente (`config={"topojsonURL": "app/static/"}` no
  `st.plotly_chart`).

## Contexto estadual, casos por município e recomendações

A aba "Contexto e recomendações" lê `fontes_datathon/contexto.json` (cards de contexto
estadual, 5 casos por município com notícia e fonte, e 3 recomendações). A equipe edita
esse arquivo sem tocar no código.

- O "nosso dado" de cada caso (ex.: +1.532 em material elétrico em Navegantes) vem da nova
  tabela `dados_processados/agregados/municipio_subclasse.parquet` (saldo por município x
  subclasse CNAE, só indústria), gerada pelo `pipeline.py`.
- Os termos entre chaves das recomendações (`{pct_pedido_ind}`, `{saldo_planalto}` etc.) são
  preenchidos a partir de `estado_setor`, `estado_divisao`, `municipio_setor` e da nova tabela
  `estado_escolaridade.parquet` (salário mediano de admissão por faixa de escolaridade).
- Enquanto essas tabelas não existirem (antes da primeira execução do pipeline com o CSV
  completo), a aba mostra um aviso e os textos aparecem sem os números calculados, em vez de
  quebrar o painel.

## Limites conhecidos

- Sem estoque de empregos (RAIS), não há taxa de rotatividade real. Usamos movimentos por habitante.
- Quase todas as admissões vêm com tipo "ignorado" (97), então não dá para separar primeiro emprego de reemprego.
- Os limiares dos cenários são uma convenção inicial e precisam de calibração e leitura crítica pela equipe.
- O dashboard foi aberto em navegador automatizado (Chromium, 1440 px) e as 8 abas foram conferidas por
  captura de tela com o setor padrão (Indústria). Os demais setores e larguras de tela menores (projetor,
  notebook) ainda precisam de uma conferência manual.

## Próximos passos sugeridos

1. Confirmar o tratamento de exclusões com a organização.
2. Rodar a etapa de IA e comparar as macrofamílias com a regra base.
3. Calibrar os limiares em `config.py` e validar os cenários com conhecimento do parque industrial de SC.
4. Rodar `python pipeline.py` com o CAGED completo para gerar `municipio_subclasse.parquet` e
   `estado_escolaridade.parquet` e ver a aba "Contexto e recomendações" com os números preenchidos.
5. Investigar o salto de Navegantes em material elétrico automotivo (caso "a investigar" em
   `contexto.json`) antes de citá-lo no pitch.
6. Escrever o roteiro do pitch de 3 minutos a partir das abas "Visão geral", "Ocupações" e
   "Contexto e recomendações".
7. Publicar o repositório (o CSV do CAGED não vai ao Git: tem 413 MB e o limite do GitHub é 100 MB).
