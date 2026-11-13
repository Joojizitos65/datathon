# Roteiro do pitch (3 minutos)

Rascunho para a equipe ajustar. Cerca de 400 palavras faladas, o que dá 3 minutos em ritmo
normal. Todos os números vêm de `dados_processados/agregados/` (indústria = seções B a F,
competências 2025-09 a 2026-08). A coluna "Tela" indica a seção do painel novo (`web/index.html`) a mostrar.

## Mensagem central

**A indústria de SC contrata 571 mil pessoas por ano para crescer 2,6 mil. O problema não é
abrir vaga: é segurar gente.**

## Roteiro

| Tempo | Tela | Fala |
|---|---|---|
| 0:00–0:30 | Visão geral (KPIs) | "Em 12 meses, a indústria catarinense fez 571 mil admissões e 568 mil desligamentos. Saldo: 2.645 vagas. São 216 contratações para cada vaga que fica. Santa Catarina tem a menor desocupação do país, 2,1%, então cada saída é uma vaga difícil de repor. Analisamos 3,4 milhões de movimentações do Novo CAGED para entender onde isso aperta e por quê." |
| 0:30–1:05 | Território (mapa) | "O estado está partido em dois. O litoral norte e o Oeste crescem: Itajaí soma +4.235 vagas, Chapecó +2.276, Joaçaba +1.169. Só Navegantes responde por +2.765, mais que o saldo industrial do estado inteiro; sem ela, a indústria de SC teria fechado no negativo. Do outro lado, o Planalto Norte encolhe: São Bento do Sul, Rio Negrinho, Campo Alegre e Mafra perderam juntas 1.497 vagas, com móveis e autopeças expostos ao tarifaço americano." |
| 1:05–1:35 | Setores (CNAE) | "Por setor, a mesma divisão. Alimentos abriu 4.739 vagas e materiais elétricos, 2.018. Vestuário fechou 4.571, madeira 1.391 e móveis 1.319. A indústria tradicional do Vale e do Planalto perde espaço para alimentos, naval e elétricos." |
| 1:35–2:10 | Gargalos (quadrantes) | "E como renda e escolaridade explicam? Cruzamos 348 combinações de região e setor. O salário de admissão fica entre 98% e 100% da mediana em todos os grupos, e a escolaridade em torno de 11 anos: a indústria paga parecido e exige parecido em todo o estado. O que separa o apagão é o giro: esses setores contratam 2,5 vezes mais que os estáveis, e 54% das saídas são pedido de demissão. No estado, quem entra ganha R$ 2.210 e quem sai ganhava R$ 2.301. A empresa perde o experiente e repõe com um mais barato, que também vai embora." |
| 2:10–2:50 | Contexto e recomendações | "Três ações. Um: reter antes de contratar, com progressão salarial nos primeiros 12 meses nas atividades de maior giro, alimentos e vestuário. Dois: recolocar o Planalto Norte, com requalificação rápida via SENAI e SINE para os setores que seguem contratando. Três: formar para os polos que crescem, com cursos técnicos curtos em soldagem, elétrica e manutenção em Navegantes e no Oeste." |
| 2:50–3:00 | Visão geral | "O apagão de mão de obra em SC não é falta de vaga, é excesso de giro. O painel mostra, município a município, onde agir primeiro." |

## Números de apoio (para perguntas da banca)

| Indicador | Valor | Onde está |
|---|---|---|
| Movimentações analisadas | 3.391.288 (6.128 fora da janela descartadas) | `metadados.json` |
| Saldo de SC, todos os setores | +41.394 | `metadados.json` |
| Saldo da indústria (B a F) | +2.645 (transformação +1.008, construção +1.533) | `estado_setor` |
| Admissões / desligamentos na indústria | 571.139 / 568.494 | `estado_setor` |
| Saídas a pedido na indústria | 47,7% (alimentos 56,5%, vestuário 55,7%) | `estado_setor`, `estado_divisao` |
| Correlação do saldo com renda e escolaridade | 0,01 (salário relativo) e −0,03 (anos de estudo), Spearman, 364 células | `micro_divisao` |
| Medianas por grupo: admissões por 10 mil hab. | apagão 34,8; expansão 29,3; retração 17,8; estável 14,0 | `micro_divisao` |
| Medianas por grupo: saídas a pedido | apagão 54%; expansão 50%; retração 44%; estável 47% | `micro_divisao` |
| Salário mediano, admissão x desligamento | R$ 2.210 x R$ 2.301 | `estado_setor` |
| Admitidos com superior completo | 4,2% | `estado_setor` |
| Maior saldo por 10 mil hab. (microrregião) | Itajaí +43,4; Chapecó +41,5 | `micro_setor` |
| Menor saldo por 10 mil hab. (microrregião) | São Bento do Sul −74,6 | `micro_setor` |
| Maiores saldos municipais | Navegantes +2.765; Joinville +1.527; Chapecó +1.110 | `municipio_setor` |
| Menores saldos municipais | São José −990; Blumenau −842; Gaspar −535 | `municipio_setor` |

## Cuidados antes de apresentar

1. **Navegantes.** Dos +2.765, cerca de 1.532 vêm de material elétrico automotivo, concentrados
   em julho e agosto de 2026, sem notícia que explique (caso "a investigar" em
   `contexto.json`). A frase "sem Navegantes a indústria fecharia no negativo" depende desse
   número. Confirmar antes de usar, ou trocar pela versão segura: "o estaleiro de Navegantes
   puxa as contratações".
2. **Rótulo "Sinal de apagão" em São Bento do Sul.** A regra atual marca a microrregião como
   apagão, mas ela tem o pior saldo do estado (−1.055) e o contexto é de retração (móveis,
   tarifaço). O roteiro trata como retração. Ver "Decisão pendente" no README.
3. **Ocupações.** Os saldos por macrofamília de CBO que estão hoje no painel usam a regra
   antiga. A classificação revisada (`llm/respostas/`) muda a macrofamília de 12,9% das
   movimentações industriais, então o roteiro não cita números por ocupação. Depois de rodar
   `python pipeline.py` com o CAGED completo, dá para incluir um dado de ocupação em 1:35–2:10.
4. **Filtro de exclusões (MOV x EX)** não foi aplicado porque as colunas não vieram no CSV.
   Se a banca perguntar, a resposta está no README.
5. Os dados de contexto (2,1% de desocupação, tarifaço) vêm de notícias listadas em
   `fontes_datathon/contexto.json`, não do CAGED.
