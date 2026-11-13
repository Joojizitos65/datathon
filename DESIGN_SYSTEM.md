# Sistema de design do painel (padrão UniSENAI)

Base visual do painel próprio em `web/`, que substitui o Streamlit. Este documento tem a
auditoria do que existia, os tokens, os componentes e o que falta migrar.

Para ver: abra `web/index.html` no navegador (duplo clique, sem servidor e sem internet).
Para atualizar os dados depois de rodar o pipeline: `python exportar_web.py`.

## 1. Auditoria do painel em Streamlit (`dashboard.py`)

**Gráficos revisados:** 12 | **Problemas encontrados:** 7

| Categoria | Tokens definidos | Valores soltos no código |
|---|---|---|
| Cores | 1 dicionário (`CORES`, 5 cenários) | 22 hex literais de 9 cores; azul/cinza de admitidos x desligados repetido 3 vezes; verde/vermelho de saldo repetido 2 vezes |
| Escalas de cor | nenhuma | `RdYlGn` em 2 lugares |
| Alturas de gráfico | nenhuma | 9 alturas diferentes (300 a 620 px) |
| Margens e legendas | nenhuma | 3 margens e 2 posições de legenda diferentes |
| Tipografia | nenhuma | tudo no padrão do Streamlit e do Plotly |

| Problema | Onde | O que o sistema novo faz |
|---|---|---|
| Verde x vermelho para saldo e para o mapa | barras de CNAE e CBO, mapa, mapa de calor | Não distingue para quem tem daltonismo (cerca de 8% dos homens). Trocado por azul x laranja com cinza no zero |
| "Sinal de apagão" vermelho e "Retração" laranja | cenários | As duas cores "quentes" se confundem. Cada cenário ganhou um matiz próprio, validado |
| Barras relativas com linha de saldo por cima | evolução mensal | Dois gráficos de um eixo cada: fluxo (linhas) e saldo (colunas) |
| Rótulos cortados com "…" | KPIs | Rótulo curto com nota de apoio embaixo |
| Aparência genérica | página toda | Padrão visual UniSENAI e manchete calculada dos dados |
| Depende de servidor Python | execução | Página estática: abre do disco |
| Sem tabela equivalente | todos os gráficos | Cada figura tem "Ver dados em tabela" |

## 2. Princípios

1. **Padrão UniSENAI.** O painel usa os tokens do Portal da Indústria (escala nacional): laranja SENAI, azul institucional, Inter, raios e sombra oficiais. Nenhuma cor fora da lista.
2. **A manchete vem primeiro.** A página abre com a conclusão em uma frase, calculada dos dados.
3. **Cor tem função.** Azul = expansão e saldo positivo; laranja = apagão e saldo negativo, como no slide do desafio.
4. **Nunca só cor.** Cenário sempre vem com o nome escrito; toda figura tem legenda e tabela.
5. **Funciona offline.** Sem fontes, bibliotecas ou mapas baixados da internet.
6. **Tudo sai dos tokens.** `estilo.css` e `app.js` não têm cor literal.

## 3. Tokens (`web/tokens.css`)

Os tokens oficiais (`--color-brand-senai-*`, `--color-brand-corporate-*`, `--color-neutral-*`,
`--radius-*`, `--shadow-level-1`, `--font-family-base`) estão declarados com os nomes do portal.
Os apelidos abaixo dizem a função de cada um no painel.

| Função | Apelido | Token oficial | Valor |
|---|---|---|---|
| Fundo da página | `--papel` | neutral-portal | `#F8F8F8` |
| Cartão | `--cartao` | neutral-white | `#FFFFFF` |
| Título e texto | `--tinta` | neutral-darkest | `#262626` |
| Texto de apoio e eixos | `--tinta-2`, `--tinta-3` | neutral-dark | `#646464` |
| Cabeçalho | `--capa` | corporate-darkest | `#070B1B` |
| Barra de 4 px e destaque | `--acento` | senai-pure | `#E84910` |
| Laranja em texto | `--acento-texto` | senai-darker | `#9F2D0B` |
| Links e seletor ativo | `--marca` | corporate-pure | `#164194` |
| Anel de foco | `--foco` | highlight-pure | `#F673AD` |
| Expansão, saldo positivo, admissões | `--cen-expansao`, `--pos` | corporate-pure | `#164194` |
| Apagão, saldo negativo, desligamentos | `--cen-apagao`, `--neg` | senai-pure | `#E84910` |
| Retração | `--cen-retracao` | senai-darkest | `#680C07` |
| Estável | `--cen-estavel` | corporate-light | `#9BACC3` |
| Mapa de saldo (7 passos) | `--div-1` a `--div-7` | senai pure/medium/light, neutral-lightest, corporate lighter/medium/pure | laranja → cinza → azul |
| Mapa de magnitude (5 passos) | `--seq-1` a `--seq-5` | corporate lightest → pure | azul claro → escuro |

As três cores de cenário passaram na separação para daltonismo (pior par ΔE 22) e no contraste
de 3:1 sobre branco. O azul e o vinho são mais escuros que a faixa recomendada para marcas de
gráfico; foram mantidos por serem os tons oficiais, e por isso todo cenário aparece com rótulo.
`#E84910` não é usado em texto corrido (3,89:1 sobre branco): texto laranja usa `#9F2D0B`.

**Tipografia:** Inter, com queda para a fonte do sistema (a Inter não está versionada; ver seção 7).
Tamanhos da escala oficial: 12, 14, 16, 24, 32 e 40 px. Pesos 400, 500 e 700.

**Espaço e forma:** 4, 8, 16, 24 e 32 px (48 e 64 px entre seções). Raio 16 px em cartões, 8 px em
controles e dica, 4 px em amostras. Sombra level-1. Largura de conteúdo de 1216 px.

**Sem modo escuro:** o padrão UniSENAI define só o tema claro.

## 4. Componentes

| Componente | Classe | Quando usar | Estados |
|---|---|---|---|
| Cabeçalho | `.barra`, `.nav` | Fixo no topo, fundo `#070B1B` com barra laranja de 4 px, âncoras para as seções | padrão, hover, foco |
| Abertura | `.abertura`, `h1`, `.lead` | Uma por página: manchete e resumo | – |
| Cartão | `.cartao` | Todo bloco de conteúdo | – |
| Indicador | `.cartao.kpi` | Um número com rótulo e nota. No máximo 6 por linha | – |
| Legenda | `.legenda` | Obrigatória com 2 ou mais séries | – |
| Achado | `.achado` | Uma frase de conclusão com barra laranja de 4 px à esquerda | – |
| Pergunta | `.pergunta` | Rótulo laranja acima do título do cartão, com a parte da pergunta que ele responde | – |
| Fato | `.fato`, `.par` | Um motivo com título, frase e até duas medidas em barra | – |
| Etiqueta de cenário | `.etiqueta` | Cenário em tabela: ponto colorido + nome | – |
| Seletor | `.seletor` | Trocar indicador (2 a 4 opções) | padrão, hover, selecionado (`aria-pressed`), foco |
| Dica | `.dica` | Detalhe ao passar o mouse sobre qualquer marca | visível, oculta |
| Tabela | `table`, `.num` | Dados tabulares; números à direita | – |
| Ver dados | `details.dados` | Tabela equivalente de cada figura | fechado, aberto |

Gráficos (funções em `web/app.js`):

| Função | Forma | Regras |
|---|---|---|
| `barras` | Barras horizontais a partir do zero | Até 18 px de espessura, ponta arredondada, valor na ponta, nome à esquerda |
| `linhas` | Linhas no tempo | 2 px, eixo a partir do zero, mira com os valores do mês |
| `colunas` | Colunas com sinal | Azul acima do zero, vermelho abaixo; só o extremo é rotulado |
| `quadrantes` | Dispersão com quatro quadrantes | Eixo X logarítmico, eixo Y limitado a ±20, linha vertical na mediana, rótulo em cada quadrante |
| `mapa` | Coroplético por município | Divergente para saldo (corte nos percentis 5 e 95), sequencial em quintis para magnitude |

**Faça:** use as funções existentes; ordene as barras pelo valor; escreva o título como a pergunta que o gráfico responde.
**Não faça:** dois eixos Y no mesmo gráfico; cor nova fora dos tokens; a cor da marca em dados; texto na cor da série.

## 5. Acessibilidade

- Cada SVG tem `role="img"` e `aria-label`; cada figura tem tabela equivalente.
- Navegação por teclado com o anel de foco rosa oficial; o seletor usa botões reais com `aria-pressed`.
- Respeita `prefers-reduced-motion`. Layout de uma coluna abaixo de 860 px.
- Conferido por captura de tela em 1440 px e 390 px, sem erros de console.

## 6. O que falta migrar do Streamlit

| Aba do Streamlit | Situação no painel novo |
|---|---|
| Visão geral | Migrada. A primeira tela responde à pergunta do desafio sem rolagem em 1920×1080 e 1440×900: quais regiões, quais setores e como renda e escolaridade explicam |
| Território | Migrada (mapa com 3 indicadores) |
| Setores (CNAE) | Migrado o saldo por divisão no estado; falta o recorte por microrregião |
| Renda e escolaridade | Migrada como "Gargalos": quadrantes de contratação x saldo e medianas de renda e escolaridade por grupo |
| Ocupações (CBO) | Falta (aguarda rodar o pipeline com a classificação nova) |
| Perfil | Falta |
| Contexto e recomendações | Falta |
| Metodologia | Falta |
| Filtro de setor | Falta: o painel novo mostra só a indústria (B a F) |

`dashboard.py` continua funcionando e fica como referência até a migração terminar.

## 7. Pendências do padrão UniSENAI

- **Logo.** O repositório não tem o arquivo oficial. O cabeçalho usa a palavra UniSENAI em Inter 700, como o padrão prevê; quando o arquivo chegar, ele entra no lugar, sem redesenho.
- **Fonte Inter.** Não está versionada: sem ela instalada na máquina, o navegador usa a fonte do sistema. Para garantir, coloque os arquivos da Inter em `web/` e declare `@font-face`.
- **Auditoria da seção 1** descreve o Streamlit; a tabela de cores antigas não se aplica ao painel novo.
