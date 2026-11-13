/* Painel Raio-X: desenha tudo em SVG a partir de window.DADOS (web/dados.js).
   Sem bibliotecas e sem rede, para abrir do disco no dia do pitch. */
(() => {
  "use strict";
  const D = window.DADOS;
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";

  // --- Formatação (pt-BR) ---------------------------------------------------
  const nf = (casas) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  const num = (v, casas = 0) => (v == null ? "–" : nf(casas).format(v));
  const sinal = (v, casas = 0) => (v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + nf(casas).format(Math.abs(v)));
  const reais = (v) => (v == null ? "–" : "R$ " + nf(0).format(v));
  const pct = (v, casas = 0) => (v == null ? "–" : nf(casas).format(v * 100) + "%");
  const mil = (v) => (Math.abs(v) >= 1000 ? nf(0).format(v / 1000) + " mil" : nf(0).format(v));
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const mes = (c, comAno = true) => MESES[(c % 100) - 1] + (comAno ? "/" + String(Math.floor(c / 100)).slice(2) : "");

  // --- Utilitários de SVG e DOM ----------------------------------------------
  function svg(tag, attrs = {}, pai) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (k === "text") e.textContent = v; else e.setAttribute(k, v);
    if (pai) pai.appendChild(e);
    return e;
  }
  function html(tag, attrs = {}, pai) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) if (k === "text") e.textContent = v; else e.setAttribute(k, v);
    if (pai) pai.appendChild(e);
    return e;
  }
  function tela(el, largura, altura, rotulo) {
    el.querySelector("svg")?.remove();
    const s = svg("svg", { viewBox: `0 0 ${largura} ${altura}`, role: "img", "aria-label": rotulo });
    el.prepend(s);
    return s;
  }
  /** Largura útil do contêiner: os gráficos são desenhados em pixels reais, sem esticar texto. */
  const larguraDe = (el) => Math.max(300, Math.floor(el.clientWidth));
  /** Passo "redondo" para um eixo com cerca de n marcas. */
  function passo(max, n = 4) {
    const bruto = max / n, pot = 10 ** Math.floor(Math.log10(bruto)), f = bruto / pot;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot;
  }
  /** Barra com a ponta de dado arredondada (4px) e a base reta. */
  function barraH(x0, x1, y, h, r = 4) {
    const w = Math.abs(x1 - x0); r = Math.min(r, w, h / 2); const s = x1 >= x0 ? 1 : -1;
    return `M${x0},${y}H${x1 - s * r}Q${x1},${y} ${x1},${y + r}V${y + h - r}Q${x1},${y + h} ${x1 - s * r},${y + h}H${x0}Z`;
  }
  function barraV(x, y0, y1, w, r = 4) {
    const h = Math.abs(y1 - y0); r = Math.min(r, h, w / 2); const s = y1 <= y0 ? 1 : -1;
    return `M${x},${y0}V${y1 + s * r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 + s * r}V${y0}Z`;
  }

  // --- Dica (tooltip) ---------------------------------------------------------
  const dica = $("dica");
  function mostrarDica(ev, titulo, linhas) {
    dica.replaceChildren(html("b", { text: titulo }));
    for (const [k, v] of linhas) { const d = html("div", {}, dica); html("span", { text: k }, d); html("span", { text: v }, d); }
    const m = 14, r = dica.getBoundingClientRect();
    let x = ev.clientX + m, y = ev.clientY + m;
    if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - m;
    if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - m;
    dica.style.left = Math.max(8, x) + "px"; dica.style.top = Math.max(8, y) + "px";
    dica.classList.add("visivel");
  }
  const esconderDica = () => dica.classList.remove("visivel");
  function comDica(alvo, titulo, linhas, marca, grupo) {
    alvo.addEventListener("pointermove", (ev) => {
      mostrarDica(ev, titulo, linhas);
      if (grupo) grupo.forEach((m) => m.classList.toggle("apagada", m !== marca));
    });
    alvo.addEventListener("pointerleave", () => { esconderDica(); if (grupo) grupo.forEach((m) => m.classList.remove("apagada")); });
  }

  // --- Legenda e tabela de dados ----------------------------------------------
  function legenda(el, itens, chave = "amostra") {
    el.replaceChildren();
    for (const [classe, texto] of itens) {
      const li = html("li", {}, el);
      html("span", { class: `${chave} b-${classe}` }, li);
      li.append(texto);
    }
  }
  function tabela(pai, colunas, linhas) {
    const t = html("table", {}, pai), tr = html("tr", {}, html("thead", {}, t)), corpo = html("tbody", {}, t);
    colunas.forEach((c) => html("th", { text: c.titulo, class: c.num ? "num" : "", scope: "col" }, tr));
    for (const l of linhas) {
      const r = html("tr", {}, corpo);
      colunas.forEach((c) => {
        const td = html("td", { class: c.num ? "num" : "" }, r), v = c.valor(l);
        if (v instanceof Node) td.appendChild(v); else td.textContent = v;
      });
    }
    return t;
  }
  /** Toda figura tem a tabela equivalente, recolhida, para leitor de tela e conferência. */
  function verDados(el, colunas, linhas) {
    const d = html("details", { class: "dados" }, el);
    html("summary", { text: "Ver dados em tabela" }, d);
    tabela(html("div", { class: "rolagem" }, d), colunas, linhas);
  }

  // --- Cenários -----------------------------------------------------------------
  const CENARIOS = [
    ["expansao", "Expansão acelerada"], ["apagao", "Sinal de apagão"], ["retracao", "Retração"],
    ["estavel", "Estável"], ["insuficiente", "Volume insuficiente"],
  ];
  const classeCenario = (nome) => (CENARIOS.find((c) => c[1] === nome) || CENARIOS[3])[0];
  function etiqueta(nome) {
    const s = html("span", { class: "etiqueta" });
    html("span", { class: `amostra b-${classeCenario(nome)}` }, s);
    s.append(nome);
    return s;
  }

  // --- Barras horizontais divergentes --------------------------------------------
  function barras(el, linhas, o) {
    const L = larguraDe(el), margE = Math.min(o.margemNome, L * 0.42), margD = 56, alt = o.alturaLinha, esp = 22, topo = 4;
    const H = topo + linhas.length * alt + esp;
    const s = tela(el, L, H, o.rotulo);
    const vals = linhas.map(o.valor), min = Math.min(0, ...vals), max = Math.max(0, ...vals);
    const folga = 52 * (max - min) / (L - margE - margD - 104);            // espaço para o valor na ponta
    const x = (v) => margE + ((v - (min - (min < 0 ? folga : 0))) / ((max + folga) - (min - (min < 0 ? folga : 0)))) * (L - margE - margD);
    const p = passo(Math.max(max, -min), 3);
    for (let t = Math.ceil(min / p) * p; t <= max; t += p) {
      svg("line", { class: t === 0 ? "base-linha" : "grade-linha", x1: x(t), x2: x(t), y1: topo, y2: H - esp }, s);
      svg("text", { x: x(t), y: H - 6, "text-anchor": "middle", text: o.eixo(t) }, s);
    }
    const marcas = [], h = Math.min(18, alt - 6);
    linhas.forEach((l, i) => {
      const v = o.valor(l), y = topo + i * alt + (alt - h) / 2;
      const cabem = Math.floor((margE - 14) / 6.3), nome = o.nome(l);
      svg("text", { class: "nome", x: margE - 10, y: y + h / 2 + 4, "text-anchor": "end", text: nome.length > cabem ? nome.slice(0, cabem - 1).trimEnd() + "…" : nome }, s);
      const m = svg("path", { class: `marca f-${o.classe(l)}`, d: barraH(x(0), x(v), y, h) }, s);
      svg("text", { class: "valor", x: x(v) + (v >= 0 ? 6 : -6), y: y + h / 2 + 4, "text-anchor": v >= 0 ? "start" : "end", text: o.rotuloValor(l) }, s);
      marcas.push(m);
      const alvo = svg("rect", { class: "alvo", x: 0, y: topo + i * alt, width: L, height: alt }, s);
      comDica(alvo, o.nome(l), o.dica(l), m, marcas);
    });
  }

  // --- Linhas (fluxo mensal) -------------------------------------------------------
  function linhas(el, dados, series, rotulo) {
    const L = larguraDe(el), H = 210, mE = 44, mD = 12, mT = 10, mB = 24;
    const s = tela(el, L, H, rotulo);
    const max = Math.max(...dados.flatMap((d) => series.map((se) => d[se.chave]))), p = passo(max, 4), teto = Math.ceil(max / p) * p;
    const x = (i) => mE + (i / (dados.length - 1)) * (L - mE - mD), y = (v) => mT + (1 - v / teto) * (H - mT - mB);
    for (let t = 0; t <= teto; t += p) {
      svg("line", { class: t === 0 ? "base-linha" : "grade-linha", x1: mE, x2: L - mD, y1: y(t), y2: y(t) }, s);
      svg("text", { x: mE - 6, y: y(t) + 4, "text-anchor": "end", text: t === 0 ? "0" : nf(0).format(t / 1000) + " mil" }, s);
    }
    dados.forEach((d, i) => { if (i % 2 === 0) svg("text", { x: x(i), y: H - 6, "text-anchor": i === 0 ? "start" : "middle", text: mes(d.competencia, i === 0 || d.competencia % 100 === 1) }, s); });
    for (const se of series) {
      svg("path", { class: `linha l-${se.classe}`, d: dados.map((d, i) => (i ? "L" : "M") + x(i) + "," + y(d[se.chave])).join("") }, s);
    }
    const mira = svg("line", { class: "mira", y1: mT, y2: H - mB, visibility: "hidden" }, s);
    const pontos = series.map((se) => svg("circle", { class: `ponto f-${se.classe}`, r: 5, visibility: "hidden" }, s));
    const alvo = svg("rect", { class: "alvo", x: mE, y: mT, width: L - mE - mD, height: H - mT - mB }, s);
    alvo.addEventListener("pointermove", (ev) => {
      const r = s.getBoundingClientRect(), px = (ev.clientX - r.left) * (L / r.width);
      const i = Math.max(0, Math.min(dados.length - 1, Math.round(((px - mE) / (L - mE - mD)) * (dados.length - 1)))), d = dados[i];
      mira.setAttribute("x1", x(i)); mira.setAttribute("x2", x(i)); mira.setAttribute("visibility", "visible");
      pontos.forEach((pt, k) => { pt.setAttribute("cx", x(i)); pt.setAttribute("cy", y(d[series[k].chave])); pt.setAttribute("visibility", "visible"); });
      mostrarDica(ev, mes(d.competencia), [...series.map((se) => [se.nome, num(d[se.chave])]), ["Saldo", sinal(d.saldo)]]);
    });
    alvo.addEventListener("pointerleave", () => { esconderDica(); mira.setAttribute("visibility", "hidden"); pontos.forEach((pt) => pt.setAttribute("visibility", "hidden")); });
  }

  // --- Colunas (saldo mensal) --------------------------------------------------------
  function colunas(el, dados, rotulo) {
    const L = larguraDe(el), H = 170, mE = 44, mD = 12, mT = 16, mB = 24;
    const s = tela(el, L, H, rotulo);
    const vals = dados.map((d) => d.saldo), ext = Math.max(...vals.map(Math.abs)), p = passo(ext, 2);
    const max = Math.ceil(Math.max(0, ...vals) / p) * p, min = Math.floor(Math.min(0, ...vals) / p) * p;
    const y = (v) => mT + ((max - v) / (max - min)) * (H - mT - mB), faixa = (L - mE - mD) / dados.length, w = Math.min(22, faixa - 4);
    for (let t = min; t <= max; t += p) {
      svg("line", { class: t === 0 ? "base-linha" : "grade-linha", x1: mE, x2: L - mD, y1: y(t), y2: y(t) }, s);
      svg("text", { x: mE - 6, y: y(t) + 4, "text-anchor": "end", text: t === 0 ? "0" : sinal(t / 1000) + " mil" }, s);
    }
    const marcas = [], extremo = dados.reduce((a, d) => (Math.abs(d.saldo) > Math.abs(a.saldo) ? d : a));
    dados.forEach((d, i) => {
      const cx = mE + i * faixa + faixa / 2;
      const m = svg("path", { class: `marca f-${d.saldo >= 0 ? "pos" : "neg"}`, d: barraV(cx - w / 2, y(0), y(d.saldo), w) }, s);
      marcas.push(m);
      if (i % 2 === 0) svg("text", { x: cx, y: H - 6, "text-anchor": "middle", text: mes(d.competencia, i === 0 || d.competencia % 100 === 1) }, s);
      if (d === extremo) svg("text", { class: "valor", x: cx + w / 2 + 5, y: y(d.saldo) - (d.saldo < 0 ? 2 : -10), text: sinal(d.saldo) }, s);
      comDica(svg("rect", { class: "alvo", x: cx - faixa / 2, y: mT, width: faixa, height: H - mT - mB }, s), mes(d.competencia),
        [["Saldo", sinal(d.saldo)], ["Admissões", num(d.admissoes)], ["Desligamentos", num(d.desligamentos)]], m, marcas);
    });
  }

  // --- Quadrantes (dispersão) ---------------------------------------------------------
  const mediana = (v) => { const o = v.filter((x) => x != null).sort((a, b) => a - b); return o.length ? (o[(o.length - 1) >> 1] + o[o.length >> 1]) / 2 : null; };
  function quadrantes(el, pontos) {
    const L = larguraDe(el), H = Math.min(520, Math.max(340, L * 0.68)), mE = 48, mD = 16, mT = 24, mB = 44;
    const s = tela(el, L, H, "Admissões por habitante contra saldo por habitante, por microrregião e setor");
    const X0 = 1, X1 = 400, LIM = 20, lg = Math.log10;
    const x = (v) => mE + ((lg(Math.min(X1, Math.max(X0, v))) - lg(X0)) / (lg(X1) - lg(X0))) * (L - mE - mD);
    const y = (v) => mT + ((LIM - Math.min(LIM, Math.max(-LIM, v))) / (2 * LIM)) * (H - mT - mB);
    for (const t of [-20, -10, 0, 10, 20]) {
      svg("line", { class: t === 0 ? "base-linha" : "grade-linha", x1: mE, x2: L - mD, y1: y(t), y2: y(t) }, s);
      svg("text", { x: mE - 6, y: y(t) + 4, "text-anchor": "end", text: (Math.abs(t) === LIM ? (t > 0 ? "≥ " : "≤ ") : "") + sinal(t) }, s);
    }
    for (const t of [1, 3, 10, 30, 100, 300]) svg("text", { x: x(t), y: H - mB + 16, "text-anchor": "middle", text: num(t) }, s);
    const corte = mediana(pontos.map((p) => p.adm10));
    svg("line", { class: "base-linha", x1: x(corte), x2: x(corte), y1: mT, y2: H - mB, "stroke-dasharray": "0" }, s);
    svg("text", { class: "eixo-titulo", x: (mE + L - mD) / 2, y: H - 6, "text-anchor": "middle", text: "Admissões por 10 mil habitantes (escala logarítmica) →" }, s);
    svg("text", { class: "eixo-titulo", x: mE, y: 12, text: "↑ Saldo por 10 mil habitantes" }, s);
    svg("text", { class: "quadrante", x: L - mD - 4, y: mT + 16, "text-anchor": "end", text: "Contrata muito e cresce" }, s);
    svg("text", { class: "quadrante", x: L - mD - 4, y: H - mB - 8, "text-anchor": "end", text: "Contrata muito e encolhe" }, s);
    svg("text", { class: "quadrante", x: mE + 6, y: mT + 16, text: "Contrata pouco e cresce" }, s);
    svg("text", { class: "quadrante", x: mE + 6, y: H - mB - 8, text: "Contrata pouco e encolhe" }, s);
    const ordem = ["Estável", "Retração", "Expansão acelerada", "Sinal de apagão"], marcas = [];
    [...pontos].sort((a, b) => ordem.indexOf(a.cenario) - ordem.indexOf(b.cenario)).forEach((p) => {
      const c = svg("circle", { class: `marca bolha f-${classeCenario(p.cenario)}`, cx: x(p.adm10), cy: y(p.saldo10), r: p.cenario === "Estável" ? 4 : 5.5 }, s);
      marcas.push(c);
      comDica(c, `${p.micro} · ${p.divisao}`, [["Cenário", p.cenario], ["Admissões / 10 mil hab.", num(p.adm10, 1)], ["Saldo / 10 mil hab.", sinal(p.saldo10, 1)],
        ["Saldo", sinal(p.saldo)], ["Salário adm. / mediana do setor", num(p.sal_rel, 2)], ["Anos de estudo (admitidos)", num(p.anos, 1)], ["Saídas a pedido", pct(p.pct_pedido)]], c, marcas);
    });
  }

  // --- Mapa coroplético ----------------------------------------------------------------
  const INDICADORES = [
    { chave: "saldo10", nome: "Saldo por habitante", titulo: "Saldo de vagas por 10 mil habitantes", tipo: "div", fmt: (v) => sinal(v, 1),
      apoio: "Azul: mais admissões que desligamentos. Laranja: o contrário. Escala cortada nos percentis 5 e 95." },
    { chave: "adm10", nome: "Contratações", titulo: "Admissões por 10 mil habitantes", tipo: "seq", fmt: (v) => num(v, 0),
      apoio: "Quanto mais escuro, mais a indústria local contrata em relação à população. Faixas por quintil." },
    { chave: "sal_adm", nome: "Salário de admissão", titulo: "Salário mediano de admissão", tipo: "seq", fmt: reais,
      apoio: "Mediana dos salários de admissão na indústria do município. Faixas por quintil." },
  ];
  const quantil = (ord, q) => ord[Math.min(ord.length - 1, Math.max(0, Math.round(q * (ord.length - 1))))];
  function mapa(ind) {
    const porId = new Map(D.municipios.map((m) => [m.id, m]));
    const vals = D.municipios.map((m) => m[ind.chave]).filter((v) => v != null).sort((a, b) => a - b);
    let classe, rotulos;
    if (ind.tipo === "div") {
      const lim = Math.max(Math.abs(quantil(vals, 0.05)), Math.abs(quantil(vals, 0.95))), cortes = [-5, -3, -1, 1, 3, 5].map((k) => (k * lim) / 7);
      classe = (v) => "div-" + (1 + cortes.filter((c) => v > c).length);
      rotulos = [ind.fmt(-lim), "0", ind.fmt(lim)];
    } else {
      const cortes = [0.2, 0.4, 0.6, 0.8].map((q) => quantil(vals, q));
      classe = (v) => "seq-" + (1 + cortes.filter((c) => v > c).length);
      rotulos = [ind.fmt(vals[0]), ind.fmt(quantil(vals, 0.5)), ind.fmt(vals[vals.length - 1])];
    }
    $("mapa-titulo").textContent = ind.titulo; $("mapa-apoio").textContent = ind.apoio;
    const esc = $("mapa-escala"); esc.replaceChildren();
    html("span", { text: rotulos[0] }, esc);
    const passos = html("span", { class: "passos" }, esc);
    for (let i = 1; i <= (ind.tipo === "div" ? 7 : 5); i++) html("i", { class: `${ind.tipo}-${i}` }, passos);
    html("span", { text: rotulos[2] }, esc);
    html("span", { text: ind.tipo === "div" ? "· cinza: perto de zero" : `· mediana ${rotulos[1]}` }, esc);

    // Projeção equirretangular com correção de cosseno na latitude média (bom o bastante para um estado).
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const f of D.malha) for (const a of f.aneis) for (const [x, y] of a) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    const k = Math.cos(((y0 + y1) / 2) * Math.PI / 180), L = 1100, esc2 = L / ((x1 - x0) * k), H = (y1 - y0) * esc2;
    const s = tela($("g-mapa"), L, Math.ceil(H), ind.titulo + ", por município");
    for (const f of D.malha) {
      const m = porId.get(f.id), v = m ? m[ind.chave] : null;
      const d = f.aneis.map((a) => a.map(([x, y], i) => (i ? "L" : "M") + ((x - x0) * k * esc2).toFixed(1) + "," + ((y1 - y) * esc2).toFixed(1)).join("") + "Z").join("");
      const pth = svg("path", { class: "municipio " + (v == null ? "sem-dado" : classe(v)), d, "fill-rule": "evenodd" }, s);
      if (m) comDica(pth, m.nome, [["Microrregião", m.micro || "–"], ["Saldo", sinal(m.saldo)], ["Saldo / 10 mil hab.", sinal(m.saldo10, 1)],
        ["Admissões / 10 mil hab.", num(m.adm10)], ["Salário de admissão", reais(m.sal_adm)]]);
    }
  }

  // --- Montagem da página -----------------------------------------------------------------
  const E = D.estado, [ini, fim] = D.meta.janela;
  $("periodo").textContent = `${mes(ini)} a ${mes(fim)} · ${num(D.meta.linhas)} movimentações`;
  $("manchete").textContent = `${mil(E.admissoes)} contratações para crescer ${num(E.saldo)} vagas`;
  $("lead").textContent = `Em 12 meses a indústria catarinense admitiu ${num(E.admissoes)} pessoas e desligou ${num(E.desligamentos)}. ` +
    `${pct(E.pct_pedido)} das saídas foram a pedido do trabalhador, e quem entra recebe ${reais(E.sal_adm)} contra ${reais(E.sal_desl)} de quem sai. ` +
    `O gargalo não é abrir vaga: é segurar gente.`;

  const nCen = (nome) => D.micro.filter((m) => m.cenario === nome).length;
  const KPIS = [
    ["Saldo em 12 meses", sinal(E.saldo), "admissões menos desligamentos"],
    ["Saldo por 10 mil hab.", sinal(E.saldo10, 1), "população estimada de 2026"],
    ["Salário de admissão", reais(E.sal_adm), `mediana · desligados: ${reais(E.sal_desl)}`],
    ["Saídas a pedido", pct(E.pct_pedido), "dos desligamentos"],
    ["Em expansão", num(nCen("Expansão acelerada")), `de ${D.micro.length} microrregiões`],
    ["Em retração ou apagão", num(nCen("Retração") + nCen("Sinal de apagão")), `de ${D.micro.length} microrregiões`],
  ];
  for (const [rot, val, nota] of KPIS) {
    const c = html("div", { class: "cartao kpi" }, $("kpis"));
    html("div", { class: "rotulo", text: rot }, c); html("div", { class: "valor", text: val }, c); html("div", { class: "nota", text: nota }, c);
  }

  const micro = [...D.micro].sort((a, b) => b.saldo10 - a.saldo10);
  const divisoes = [...D.divisoes].sort((a, b) => b.saldo - a.saldo);
  const SERIES = [{ chave: "admissoes", nome: "Admissões", classe: "admissoes" }, { chave: "desligamentos", nome: "Desligamentos", classe: "desligamentos" }];
  legenda($("leg-micro"), CENARIOS.filter(([, n]) => nCen(n) > 0));
  legenda($("leg-fluxo"), SERIES.map((s) => [s.classe, s.nome]), "amostra linha-chave");
  legenda($("leg-setores"), [["pos", "Abriu vagas"], ["neg", "Fechou vagas"]]);

  function desenhar() {
  barras($("g-micro"), micro, {
    rotulo: "Saldo por 10 mil habitantes em cada microrregião", margemNome: 150, alturaLinha: 26,
    valor: (m) => m.saldo10, nome: (m) => m.nome, classe: (m) => classeCenario(m.cenario),
    rotuloValor: (m) => sinal(m.saldo10, 1), eixo: (t) => sinal(t),
    dica: (m) => [["Cenário", m.cenario], ["Saldo", sinal(m.saldo)], ["Saldo / 10 mil hab.", sinal(m.saldo10, 1)],
      ["Salário de admissão", reais(m.sal_adm)], ["Saídas a pedido", pct(m.pct_pedido)]],
  });
  linhas($("g-fluxo"), D.mensal, SERIES, "Admissões e desligamentos mensais na indústria");
  colunas($("g-saldo"), D.mensal, "Saldo mensal de vagas na indústria");
  quadrantes($("g-quad"), D.celulas);
  barras($("g-setores"), divisoes, {
    rotulo: "Saldo de vagas por divisão CNAE", margemNome: 380, alturaLinha: 24,
    valor: (d) => d.saldo, nome: (d) => d.nome, classe: (d) => (d.saldo >= 0 ? "pos" : "neg"),
    rotuloValor: (d) => sinal(d.saldo), eixo: (t) => (t === 0 ? "0" : sinal(t / 1000) + " mil"),
    dica: (d) => [["Divisão CNAE", String(d.codigo)], ["Saldo", sinal(d.saldo)], ["Admissões", num(d.admissoes)],
      ["Salário de admissão", reais(d.sal_adm)], ["Saídas a pedido", pct(d.pct_pedido)]],
  });
  }
  desenhar();
  let espera;
  addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(desenhar, 150); });

  // Gargalos: legenda, achado e medianas por cenário
  const GRUPOS = ["Sinal de apagão", "Expansão acelerada", "Retração", "Estável"];
  const resumo = GRUPOS.map((g) => { const c = D.celulas.filter((p) => p.cenario === g);
    return { g, n: c.length, adm10: mediana(c.map((p) => p.adm10)), pedido: mediana(c.map((p) => p.pct_pedido)), sal: mediana(c.map((p) => p.sal_rel)), anos: mediana(c.map((p) => p.anos)) }; });
  legenda($("leg-quad"), CENARIOS.filter(([, n]) => GRUPOS.includes(n)));
  $("quad-apoio").textContent = `${num(D.celulas.length)} combinações de microrregião e divisão CNAE com ao menos 200 movimentações. Linha vertical: mediana das admissões. Valores além de ±20 ficam na borda.`;
  const sals = resumo.map((r) => r.sal), anosR = resumo.map((r) => r.anos), ap = resumo[0], es = resumo[3];
  const achado = $("achado");
  achado.append("Renda e escolaridade são quase iguais nos quatro grupos: salário de admissão entre ", html("b", { text: `${pct(Math.min(...sals))} e ${pct(Math.max(...sals))}` }),
    " da mediana do setor e ", html("b", { text: `${num(Math.min(...anosR), 1)} a ${num(Math.max(...anosR), 1)} anos` }), " de estudo. O que separa o apagão é o giro: ",
    html("b", { text: `${num(ap.adm10 / es.adm10, 1)}×` }), ` mais admissões por habitante que os estáveis e ${pct(ap.pedido)} das saídas a pedido.`);
  tabela($("t-quad"), [
    { titulo: "Grupo", valor: (r) => etiqueta(r.g) },
    { titulo: "Adm./10 mil", num: true, valor: (r) => num(r.adm10, 1) }, { titulo: "A pedido", num: true, valor: (r) => pct(r.pedido) },
    { titulo: "Salário", num: true, valor: (r) => pct(r.sal) }, { titulo: "Estudo", num: true, valor: (r) => num(r.anos, 1) + " a" }], resumo);
  html("p", { class: "apoio", text: "Adm./10 mil: admissões por 10 mil habitantes. A pedido: parcela dos desligamentos pedidos pelo trabalhador. Salário: admissão em relação à mediana estadual do setor. Estudo: anos de estudo dos admitidos." }, $("t-quad")).style.margin = "16px 0 0";
  verDados($("g-quad"), [
    { titulo: "Microrregião", valor: (p) => p.micro }, { titulo: "Divisão CNAE", valor: (p) => p.divisao }, { titulo: "Cenário", valor: (p) => p.cenario },
    { titulo: "Adm. / 10 mil", num: true, valor: (p) => num(p.adm10, 1) }, { titulo: "Saldo / 10 mil", num: true, valor: (p) => sinal(p.saldo10, 1) }],
    [...D.celulas].sort((a, b) => b.adm10 - a.adm10));

  verDados($("g-micro"), [
    { titulo: "Microrregião", valor: (m) => m.nome }, { titulo: "Cenário", valor: (m) => m.cenario },
    { titulo: "Saldo", num: true, valor: (m) => sinal(m.saldo) }, { titulo: "Saldo / 10 mil", num: true, valor: (m) => sinal(m.saldo10, 1) },
    { titulo: "Admissões", num: true, valor: (m) => num(m.admissoes) }], micro);

  verDados($("g-saldo"), [
    { titulo: "Mês", valor: (d) => mes(d.competencia) }, { titulo: "Admissões", num: true, valor: (d) => num(d.admissoes) },
    { titulo: "Desligamentos", num: true, valor: (d) => num(d.desligamentos) }, { titulo: "Saldo", num: true, valor: (d) => sinal(d.saldo) }], D.mensal);

  let atual = INDICADORES[0];
  const botoes = INDICADORES.map((ind) => {
    const b = html("button", { type: "button", text: ind.nome, "aria-pressed": String(ind === atual) }, $("mapa-seletor"));
    b.addEventListener("click", () => { atual = ind; botoes.forEach((x) => x.setAttribute("aria-pressed", String(x === b))); mapa(ind); });
    return b;
  });
  mapa(atual);

  verDados($("g-setores"), [
    { titulo: "Divisão", valor: (d) => `${d.codigo} · ${d.nome}` }, { titulo: "Saldo", num: true, valor: (d) => sinal(d.saldo) },
    { titulo: "Admissões", num: true, valor: (d) => num(d.admissoes) }, { titulo: "Salário adm.", num: true, valor: (d) => reais(d.sal_adm) },
    { titulo: "Saídas a pedido", num: true, valor: (d) => pct(d.pct_pedido) }], divisoes);

  const ORDEM = ["Sinal de apagão", "Retração", "Expansão acelerada"];
  const alertas = D.micro.filter((m) => ORDEM.includes(m.cenario)).sort((a, b) => ORDEM.indexOf(a.cenario) - ORDEM.indexOf(b.cenario) || a.saldo10 - b.saldo10);
  tabela($("t-alertas-tabela"), [
    { titulo: "Microrregião", valor: (m) => m.nome }, { titulo: "Cenário", valor: (m) => etiqueta(m.cenario) },
    { titulo: "Saldo", num: true, valor: (m) => sinal(m.saldo) }, { titulo: "Saldo / 10 mil", num: true, valor: (m) => sinal(m.saldo10, 1) },
    { titulo: "Salário adm.", num: true, valor: (m) => reais(m.sal_adm) }, { titulo: "Saídas a pedido", num: true, valor: (m) => pct(m.pct_pedido) },
    { titulo: "Fatores apontados", valor: (m) => m.fatores || "–" }], alertas);

  $("rodape").textContent = `Fonte: Novo CAGED (movimentações de ${mes(ini)} a ${mes(fim)}) e IBGE. Indústria = seções B a F da CNAE. ` +
    `Dados processados em ${D.meta.gerado_em.slice(0, 10).split("-").reverse().join("/")}. Cenários são uma classificação relativa entre microrregiões (ver README).`;
})();
