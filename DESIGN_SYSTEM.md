# Sistema de design "Raio-X"

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
| Verde x vermelho para saldo e para o mapa | barras de CNAE e CBO, mapa, mapa de calor | Não distingue para quem tem daltonismo (cerca de 8% dos homens). Trocado por azul x vermelho com cinza no zero |
| "Sinal de apagão" vermelho e "Retração" laranja | cenários | As duas cores "quentes" se confundem. Cada cenário ganhou um matiz próprio, validado |
| Barras relativas com linha de saldo por cima | evolução mensal | Dois gráficos de um eixo cada: fluxo (linhas) e saldo (colunas) |
| Rótulos cortados com "…" | KPIs | Rótulo curto com nota de apoio embaixo |
| Aparência genérica | página toda | Identidade própria: papel quente, título em serifa, manchete calculada dos dados |
| Depende de servidor Python | execução | Página estática: abre do disco |
| Sem tabela equivalente | todos os gráficos | Cada figura tem "Ver dados em tabela" |

## 2. Princípios

1. **A manchete vem primeiro.** A página abre com a conclusão em uma frase, calculada dos dados.
2. **Cor tem função.** Cada cor significa uma coisa só: cenário, polaridade do saldo ou magnitude. A cor da marca nunca aparece em dados.
3. **Nunca só cor.** Cenário sempre vem com o nome escrito; toda figura tem legenda e tabela.
4. **Funciona offline.** Sem fontes, bibliotecas ou mapas baixados da internet.
5. **Tudo sai dos tokens.** `estilo.css` e `app.js` não têm cor literal: mudar a identidade é editar `tokens.css`.

## 3. Tokens (`web/tokens.css`)

### Cor

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--papel` | `#f5f2ec` | `#0f1113` | Fundo da página |
| `--cartao` | `#fdfcfa` | `#1a1c1e` | Superfície de cartões e gráficos |
| `--tinta` / `--tinta-2` / `--tinta-3` | `#14181d` / `#4b525a` / `#7d8289` | `#f0efec` / `#c3c2b7` / `#8b8a84` | Texto principal, secundário e notas |
| `--fio` / `--eixo` | `#e4dfd5` / `#c5c0b5` | `#2c2e30` / `#3a3c3e` | Grade e linha de base |
| `--marca` | `#0e4f5c` | `#7cc4d1` | Navegação, foco e destaque de interface |
| `--cen-expansao` | `#2a78d6` | `#3987e5` | Expansão acelerada |
| `--cen-apagao` | `#1baf7a` | `#199e70` | Sinal de apagão |
| `--cen-retracao` | `#eb6834` | `#d95926` | Retração |
| `--cen-estavel` | `#b3b0a8` | `#5c5d5c` | Estável (recua de propósito) |
| `--pos` / `--neg` | `#2a78d6` / `#d03b3b` | `#3987e5` / `#e66767` | Saldo positivo e negativo |
| `--div-1` a `--div-7` | vermelho → cinza → azul | idem | Mapa de saldo (divergente) |
| `--seq-1` a `--seq-5` | azul claro → escuro | azul escuro → claro | Mapas de magnitude |

As cores de cenário e o par positivo/negativo passaram no validador de paleta (separação para
daltonismo, distinção em visão normal e contraste) nos dois modos, sobre a superfície real dos
cartões. Única ressalva: o verde de "Sinal de apagão" tem contraste 2,75:1 no modo claro, abaixo
de 3:1, e por isso ele sempre aparece com rótulo de texto.

### Tipografia

| Token | Valor | Uso |
|---|---|---|
| `--fonte-titulo` | Iowan Old Style, Palatino, Georgia (serifa do sistema) | Manchete, títulos de seção, selo |
| `--fonte` | system-ui, Segoe UI, Roboto | Todo o resto, inclusive números |
| `--t-h1` / `--t-h2` | 44 px / 24 px | Manchete e seção |
| `--t-numero` | 30 px | Valor de indicador |
| `--t-lead` / `--t-corpo` / `--t-nota` | 17 / 14 / 12 px | Abertura, corpo, notas e eixos |

### Espaço, forma e movimento

| Token | Valor |
|---|---|
| `--e1` a `--e8` | 4, 8, 12, 16, 24, 32, 48, 72 px |
| `--raio` / `--raio-p` | 10 px (cartão) / 6 px (controles e dica) |
| `--sombra` | sombra leve em dois níveis (desligada no modo escuro) |
| `--rapido` | 120 ms |
| `--largura` | 1200 px de conteúdo |

## 4. Componentes

| Componente | Classe | Quando usar | Estados |
|---|---|---|---|
| Barra de navegação | `.barra`, `.nav` | Fixa no topo, âncoras para as seções | padrão, hover, foco |
| Abertura | `.abertura`, `h1`, `.lead` | Uma por página: manchete e resumo | – |
| Cartão | `.cartao` | Todo bloco de conteúdo | – |
| Indicador | `.cartao.kpi` | Um número com rótulo e nota. No máximo 6 por linha | – |
| Legenda | `.legenda` | Obrigatória com 2 ou mais séries | – |
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
| `mapa` | Coroplético por município | Divergente para saldo (corte nos percentis 5 e 95), sequencial em quintis para magnitude |

**Faça:** use as funções existentes; ordene as barras pelo valor; escreva o título como a pergunta que o gráfico responde.
**Não faça:** dois eixos Y no mesmo gráfico; cor nova fora dos tokens; a cor da marca em dados; texto na cor da série.

## 5. Acessibilidade

- Cada SVG tem `role="img"` e `aria-label`; cada figura tem tabela equivalente.
- Navegação por teclado com foco visível; o seletor usa botões reais com `aria-pressed`.
- Modo escuro automático pelo sistema; `data-theme="light"` ou `"dark"` no `<html>` força um deles.
- Respeita `prefers-reduced-motion`. Layout de uma coluna abaixo de 860 px.
- Conferido por captura de tela em 1440 px (claro e escuro) e 390 px, sem erros de console.

## 6. O que falta migrar do Streamlit

| Aba do Streamlit | Situação no painel novo |
|---|---|
| Visão geral | Migrada (Panorama e Alertas) |
| Território | Migrada (mapa com 3 indicadores) |
| Setores (CNAE) | Migrado o saldo por divisão no estado; falta o recorte por microrregião |
| Renda e escolaridade | Falta |
| Ocupações (CBO) | Falta (aguarda rodar o pipeline com a classificação nova) |
| Perfil | Falta |
| Contexto e recomendações | Falta |
| Metodologia | Falta |
| Filtro de setor | Falta: o painel novo mostra só a indústria (B a F) |

`dashboard.py` continua funcionando e fica como referência até a migração terminar.

## 7. Decisões em aberto

- **Nome e selo.** "Raio-X" veio do título do projeto; trocar é editar `index.html`.
- **Cor da marca.** O azul-petróleo `--marca` é uma proposta. Se a equipe tiver uma cor própria, basta trocar o token.
- **Fonte.** Uma fonte própria daria mais personalidade, mas precisa ser versionada em `web/` para funcionar offline.
