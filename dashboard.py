"""Painel de Inteligência Operacional e Territorial - Mercado de Trabalho Industrial em SC.

Uso:
    streamlit run dashboard.py

Lê somente as tabelas agregadas geradas por `pipeline.py` (dados_processados/agregados).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config as cfg
import contexto as ctxmod
import referencias as ref

PASTA = cfg.DIR_AGREGADOS
CORES = {
    "Expansão acelerada": "#2e7d32",
    "Sinal de apagão": "#c62828",
    "Retração": "#ef6c00",
    "Estável": "#9e9e9e",
    "Volume insuficiente": "#cfd8dc",
}
ORDEM_CENARIO = list(CORES)
IND = cfg.SETOR_INDUSTRIA

# Mapa de municípios (aba Território): diagnóstico de cada município no setor escolhido.
CORES_DIAG = {  # mesma paleta do mapa original (azul = cresce, vermelho = encolhe, laranja = gira demais)
    "Expansão acelerada": "#2a78d6",
    "Alta rotatividade": "#eb6834",
    "Retração": "#a32d2d",
    "Estável": "#cfcfcb",
    "Dados insuficientes": "#ececea",
}
# Escala divergente: vermelho (perda) - claro (zero) - azul (ganho).
ESCALA_DIVERGENTE = [[0, "#7f1f1f"], [0.25, "#d34a47"], [0.45, "#f3c4c2"], [0.5, "#f4f4f5"],
                     [0.55, "#b7d3f6"], [0.75, "#2a78d6"], [1, "#104281"]]
ESCALA_SEQUENCIAL = [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]]
COR_SEM_DADO = "#ececea"
# Rótulos de referência no mapa: (latitude, longitude, posição do texto)
CIDADES = {
    "Joinville": (-26.273, -48.996, "middle right"), "Blumenau": (-26.864, -49.098, "middle left"),
    "Navegantes": (-26.826, -48.73, "middle right"), "Florianópolis": (-27.614, -48.492, "middle right"),
    "Criciúma": (-28.718, -49.387, "middle left"), "Lages": (-27.96, -50.353, "middle right"),
    "Mafra": (-26.215, -49.878, "top center"), "Joaçaba": (-27.152, -51.587, "bottom center"),
    "Chapecó": (-27.116, -52.661, "bottom center"), "São Miguel do Oeste": (-26.728, -53.509, "top right"),
}

st.set_page_config(page_title="Raio-X do Trabalho Industrial em SC", layout="wide")


# --- Carga ------------------------------------------------------------------
@st.cache_data
def carregar(nome: str) -> pd.DataFrame:
    return pd.read_parquet(PASTA / f"{nome}.parquet")


@st.cache_data
def metadados() -> dict:
    return json.loads((PASTA / "metadados.json").read_text(encoding="utf-8"))


@st.cache_data
def malha() -> dict:
    return ref.malha_municipios()


@st.cache_data
def contorno(codigo_ibge: str) -> tuple[list, list]:
    """Anéis externos do município como uma linha (lon, lat) separada por None.

    Serve para desenhar o destaque do município selecionado sobre o mapa sem bloquear hover e clique.
    """
    for f in malha()["features"]:
        if f["properties"]["codarea"] == codigo_ibge:
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            lon, lat = [], []
            for poly in polys:
                lon += [p[0] for p in poly[0]] + [None]
                lat += [p[1] for p in poly[0]] + [None]
            return lon, lat
    return [], []


if not (PASTA / "metadados.json").exists():
    st.error("Tabelas agregadas não encontradas. Rode `python pipeline.py` antes de abrir o painel.")
    st.stop()


def fmt(x, casas: int = 0, sinal: bool = False) -> str:
    """Formata número no padrão brasileiro (1.234,5)."""
    if x is None or pd.isna(x):
        return "-"
    s = f"{x:+,.{casas}f}" if sinal else f"{x:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def competencia_para_data(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie.astype(str), format="%Y%m")


meta = metadados()
est_setor = carregar("estado_setor")
micro_setor = carregar("micro_setor")
dim_mun = carregar("dim_municipio")
ini, fim = meta["janela_competencias"]

# --- Filtros ----------------------------------------------------------------
nomes = dict(zip(est_setor["setor"], est_setor["setor_nome"]))
secoes = [s for s in nomes if s != IND]
industriais = [s for s in cfg.SECOES_INDUSTRIA if s in secoes]
opcoes = [IND] + industriais + sorted(s for s in secoes if s not in industriais)

st.sidebar.title("Filtros")
setor = st.sidebar.selectbox(
    "Setor", opcoes, index=0,
    format_func=lambda s: nomes[s] if s == IND else f"{s} - {nomes[s]}",
)
eh_industria = setor == IND or setor in cfg.SECOES_INDUSTRIA
st.sidebar.caption(
    f"Competências {ini} a {fim} (últimos {cfg.JANELA_MESES} meses).\n\n"
    "Fonte: Novo CAGED (movimentações) e IBGE. Detalhe por divisão CNAE e por ocupação "
    "existe apenas para a indústria (seções B a F)."
)

st.title("Raio-X do Mercado de Trabalho Industrial em Santa Catarina")
st.caption(f"Setor selecionado: **{nomes[setor]}**")

est = est_setor[est_setor["setor"] == setor].iloc[0]
ms = micro_setor[micro_setor["setor"] == setor].copy()

(aba_geral, aba_territorio, aba_setores, aba_renda, aba_cbo, aba_perfil, aba_contexto, aba_metodo) = st.tabs(
    ["Visão geral", "Território", "Setores (CNAE)", "Renda e escolaridade",
     "Ocupações (CBO)", "Perfil", "Contexto e recomendações", "Metodologia"]
)

# =============================================================================
# Visão geral
# =============================================================================
with aba_geral:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Saldo líquido (12 meses)", fmt(est["saldo"], sinal=True),
              help="Admissões menos desligamentos no período.")
    c2.metric("Saldo por 10 mil habitantes", fmt(est["saldo_por_10mil"], 1, sinal=True),
              help="Saldo dividido pela população estimada de 2026 do estado.")
    c3.metric("Salário mediano de admissão", f"R$ {fmt(est['sal_mediana_adm'], 0)}",
              help="Só registros com salário válido (ver aba Metodologia).")
    c4.metric("Desligamentos por admissão", fmt(est["razao_desl_adm"], 2),
              help="Acima de 1 indica mais saídas que entradas.")
    n_apagao = int((ms["cenario"] == "Sinal de apagão").sum())
    n_exp = int((ms["cenario"] == "Expansão acelerada").sum())
    c5.metric("Microrregiões em alerta", f"{n_apagao} apagão | {n_exp} expansão",
              help="Classificação relativa entre as microrregiões (ver aba Metodologia).")

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        st.subheader("Onde está o problema")
        d = ms[ms["cenario"] != "Volume insuficiente"].sort_values("saldo_por_10mil")
        fig = px.bar(
            d, x="saldo_por_10mil", y="microrregiao_nome", color="cenario", orientation="h",
            color_discrete_map=CORES, category_orders={"cenario": ORDEM_CENARIO},
            labels={"saldo_por_10mil": "Saldo por 10 mil habitantes", "microrregiao_nome": "", "cenario": "Cenário"},
            hover_data={"saldo": ":,", "admissoes": ":,", "desligamentos": ":,"},
        )
        fig.update_layout(height=560, legend_orientation="h", legend_y=-0.12, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    with direita:
        st.subheader("Evolução mensal")
        mensal = carregar("mensal_micro")
        mensal = mensal[mensal["setor"] == setor].groupby("competencia")[["admissoes", "desligamentos"]].sum().reset_index()
        mensal["saldo"] = mensal["admissoes"] - mensal["desligamentos"]
        mensal["mes"] = competencia_para_data(mensal["competencia"])
        fig = go.Figure()
        fig.add_bar(x=mensal["mes"], y=mensal["admissoes"], name="Admissões", marker_color="#1565c0")
        fig.add_bar(x=mensal["mes"], y=-mensal["desligamentos"], name="Desligamentos", marker_color="#90a4ae")
        fig.add_scatter(x=mensal["mes"], y=mensal["saldo"], name="Saldo", line=dict(color="#c62828", width=3))
        fig.update_layout(barmode="relative", height=300, legend_orientation="h", legend_y=-0.25,
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")

        st.subheader("Alertas")
        alertas = ms[ms["cenario"].isin(["Sinal de apagão", "Expansão acelerada"])].sort_values(
            ["cenario", "saldo_por_10mil"], ascending=[False, False])
        if alertas.empty:
            st.info("Nenhuma microrregião classificada em alerta para este setor.")
        else:
            st.dataframe(
                alertas[["microrregiao_nome", "cenario", "saldo_por_10mil", "fatores"]],
                hide_index=True, width="stretch",
                column_config={
                    "microrregiao_nome": "Microrregião", "cenario": "Cenário",
                    "saldo_por_10mil": st.column_config.NumberColumn("Saldo/10 mil", format="%.1f"),
                    "fatores": "Fatores associados",
                },
            )

# =============================================================================
# Território
# =============================================================================
with aba_territorio:
    # --- Base: os 295 municípios, com ou sem movimentação no setor escolhido ---------------------
    base_mun = dim_mun[["municipio_codigo", "codigo_ibge", "municipio_nome", "pop_estimada_2026"]].copy()
    base_mun["codigo_ibge"] = base_mun["codigo_ibge"].astype(str)
    dados_mun = carregar("municipio_setor")
    dados_mun = dados_mun[dados_mun["setor"] == setor][[
        "municipio_codigo", "admissoes", "desligamentos", "saldo", "movimentos",
        "razao_desl_adm", "pct_pedido_desl", "sal_mediana_adm"]]
    mp = base_mun.merge(dados_mun, on="municipio_codigo", how="left")
    for c in ["admissoes", "desligamentos", "saldo", "movimentos"]:
        mp[c] = mp[c].fillna(0).astype(int)
    mp["saldo_10k"] = mp["saldo"] / mp["pop_estimada_2026"] * 1e4
    mp["giro_10k"] = mp["movimentos"] / mp["pop_estimada_2026"] * 1e4

    # --- Controles --------------------------------------------------------------------------------
    metrica = st.segmented_control(
        "Colorir o mapa por",
        ["Diagnóstico", "Saldo por 10 mil hab.", "Desligamentos por admissão", "Saídas a pedido",
         "Salário de admissão"],
        default="Diagnóstico", key="metrica_mapa") or "Diagnóstico"
    c_minimo, _ = st.columns([2, 3])
    min_mov = c_minimo.slider(
        "Mín. de movimentações por município", 0, 2000, cfg.MIN_MOV_CELULA, 50, key="min_mov_mapa",
        help="Abaixo desse volume no setor, o município aparece como 'Dados insuficientes': "
             "taxas de cidades muito pequenas oscilam demais.")

    # --- Diagnóstico de cada município (relativo aos demais, no setor escolhido) ----------------
    ok = mp["movimentos"] >= max(min_mov, 1)
    if ok.sum() >= 5:
        q_alto = mp.loc[ok, "saldo_10k"].quantile(0.8)
        q_baixo = mp.loc[ok, "saldo_10k"].quantile(0.2)
        giro_alto = mp.loc[ok, "giro_10k"].quantile(0.8)
    else:
        q_alto, q_baixo, giro_alto = np.inf, -np.inf, np.inf
    mp["diag"] = np.select(
        [~ok,
         ok & (mp["saldo_10k"] >= q_alto) & (mp["saldo"] > 0),
         ok & (mp["saldo_10k"] <= q_baixo) & (mp["saldo"] < 0),
         ok & (mp["giro_10k"] >= giro_alto)],
        ["Dados insuficientes", "Expansão acelerada", "Retração", "Alta rotatividade"], "Estável")

    # Textos do hover (já no padrão brasileiro)
    mp["h_saldo"] = mp["saldo"].map(lambda x: fmt(x, 0, sinal=True))
    mp["h_10k"] = mp["saldo_10k"].map(lambda x: fmt(x, 1))
    mp["h_rot"] = mp["razao_desl_adm"].map(lambda x: fmt(x, 2))
    mp["h_ped"] = mp["pct_pedido_desl"].map(lambda x: "-" if pd.isna(x) else f"{fmt(x * 100, 0)}%")
    mp["h_sal"] = mp["sal_mediana_adm"].map(lambda x: "-" if pd.isna(x) else f"R$ {fmt(x, 0)}")
    mp["h_mov"] = mp["movimentos"].map(lambda x: fmt(x))
    HOVER = ["municipio_nome", "diag", "h_saldo", "h_10k", "h_rot", "h_ped", "h_sal", "h_mov"]
    HT = ("<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
          "Saldo: %{customdata[2]} vagas (%{customdata[3]} por 10 mil hab.)<br>"
          "Desligamentos por admissão: %{customdata[4]} · Saídas a pedido: %{customdata[5]}<br>"
          "Salário mediano de admissão: %{customdata[6]}<br>"
          "Movimentações: %{customdata[7]}<extra></extra>")

    contagem = mp["diag"].value_counts()
    st.info(
        f"**{contagem.get('Expansão acelerada', 0)} municípios em expansão acelerada** e "
        f"**{contagem.get('Retração', 0)} em retração**. Outros {contagem.get('Alta rotatividade', 0)} têm "
        f"alta rotatividade: muito movimento por habitante e pouco saldo. "
        f"Setor: {nomes[setor]}.")

    # --- Clique no mapa -> município em destaque -----------------------------------------------------
    # A seleção do clique chega em session_state antes do rerun. Só aplicamos quando o clique muda,
    # para não sobrescrever uma escolha feita depois na caixa de seleção.
    cod_por_nome = dict(zip(mp["municipio_nome"], mp["codigo_ibge"]))
    nome_por_cod = {v: k for k, v in cod_por_nome.items()}
    clique = (st.session_state.get("mapa_sel") or {}).get("selection", {}).get("points", [])
    cod_clicado = next((p.get("location") for p in clique if p.get("location")), None)
    if cod_clicado != st.session_state.get("_ult_clique_mapa"):
        st.session_state["_ult_clique_mapa"] = cod_clicado
        if cod_clicado in nome_por_cod:
            st.session_state["mun_sel_mapa"] = nome_por_cod[cod_clicado]
    mun_atual = st.session_state.get("mun_sel_mapa")

    c_mapa, c_lado = st.columns([2.15, 1], gap="large")
    with c_mapa:
        # go.Choropleth (mapa vetorial) em vez de px.choropleth_map: este último baixa o fundo
        # (tiles) de um servidor de mapas pela internet, o que deixa o painel em branco sem
        # conexão (ex.: rede do auditório no pitch). O go.Choropleth só precisa do GeoJSON dos
        # municípios (já em cache local) e do TopoJSON base do mundo, servido por static/.
        fig = go.Figure()
        comum = dict(
            geojson=malha(), featureidkey="properties.codarea",
            marker=dict(line=dict(color="white", width=0.6)), hovertemplate=HT,
            # sem esmaecer o resto do mapa quando um município é clicado (o destaque é o contorno)
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
        )
        if metrica == "Diagnóstico":
            for cat, cor in CORES_DIAG.items():
                sub = mp[mp["diag"] == cat]
                if sub.empty:
                    continue
                fig.add_trace(go.Choropleth(
                    locations=sub["codigo_ibge"], z=np.ones(len(sub)), colorscale=[[0, cor], [1, cor]],
                    showscale=False, name=cat, showlegend=True, customdata=sub[HOVER], **comum))
            fig.update_layout(legend=dict(orientation="h", x=0.0, y=0.0, yanchor="bottom",
                                          bgcolor="rgba(255,255,255,0)"))
        else:
            col, escala, centro, formato = {
                "Saldo por 10 mil hab.": ("saldo_10k", ESCALA_DIVERGENTE, 0.0, ",.0f"),
                # mais desligamentos que admissões = ruim: mesma escala, invertida (abaixo de 1 azul, acima de 1 vermelho)
                "Desligamentos por admissão": (
                    "razao_desl_adm", [[1 - p, cor] for p, cor in ESCALA_DIVERGENTE][::-1], 1.0, ".2f"),
                "Saídas a pedido": ("pct_pedido_desl", ESCALA_SEQUENCIAL, None, ".0%"),
                "Salário de admissão": ("sal_mediana_adm", ESCALA_SEQUENCIAL, None, ",.0f"),
            }[metrica]
            # Fundo cinza para todos os municípios; os com volume suficiente são pintados por cima.
            fig.add_trace(go.Choropleth(
                locations=mp["codigo_ibge"], z=np.zeros(len(mp)), colorscale=[[0, COR_SEM_DADO], [1, COR_SEM_DADO]],
                showscale=False, customdata=mp[HOVER], **comum))
            validos = mp[ok & mp[col].notna()]
            if len(validos):
                if centro is None:
                    zmin, zmax = float(validos[col].quantile(0.02)), float(validos[col].quantile(0.98))
                else:
                    lim = float((validos[col] - centro).abs().quantile(0.95)) or 1.0
                    zmin, zmax = centro - lim, centro + lim
                fig.add_trace(go.Choropleth(
                    locations=validos["codigo_ibge"], z=validos[col], colorscale=escala, zmin=zmin, zmax=zmax,
                    colorbar=dict(thickness=12, len=0.6, x=1.0, tickformat=formato, outlinewidth=0),
                    customdata=validos[HOVER], **comum))
            fig.update_layout(showlegend=False)

        # Rótulos das principais cidades
        fig.add_trace(go.Scattergeo(
            lon=[c[1] for c in CIDADES.values()], lat=[c[0] for c in CIDADES.values()],
            text=list(CIDADES), mode="markers+text", textposition=[c[2] for c in CIDADES.values()],
            marker=dict(size=4, color="#212121"), textfont=dict(size=11, color="#212121"),
            hoverinfo="skip", showlegend=False))
        # Contorno do município em destaque (linha, não preenchimento: não bloqueia hover nem clique)
        if mun_atual in cod_por_nome:
            lon_c, lat_c = contorno(cod_por_nome[mun_atual])
            if lon_c:
                fig.add_trace(go.Scattergeo(lon=lon_c, lat=lat_c, mode="lines",
                                            line=dict(color="#212121", width=2.4),
                                            hoverinfo="skip", showlegend=False))
        # O estado vai de lon -53,84 a -48,36 e lat -29,35 a -25,96. Há folga a leste para os rótulos da costa
        # e o domain reserva a faixa de baixo para a legenda do diagnóstico, que senão cobre o sul do estado.
        fig.update_geos(
            fitbounds=False, visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator",
            lonaxis_range=[-54.1, -47.35], lataxis_range=[-29.6, -25.72],
            domain=dict(x=[0, 1], y=[0.08 if metrica == "Diagnóstico" else 0, 1]))
        fig.update_layout(
            height=470, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", separators=",.",
            dragmode="pan", uirevision="mapa",  # uirevision: zoom e arraste do usuário sobrevivem aos reruns
            modebar=dict(orientation="v", bgcolor="rgba(255,255,255,0.95)"))
        st.plotly_chart(
            fig, width="stretch", key="mapa_sel", on_select="rerun", selection_mode="points",
            config={"displayModeBar": True, "displaylogo": False, "scrollZoom": False,
                    "topojsonURL": "app/static/", "modeBarButtons": [["zoomInGeo", "zoomOutGeo", "resetGeo"]]})
        st.caption(
            "Use **+ / −** no canto do mapa para dar zoom, arraste para mover e **clique num município** para "
            f"destacá-lo. Cinza claro: menos de {min_mov} movimentações no setor. Nas escalas contínuas as cores são "
            "cortadas nos percentis extremos, para que municípios muito pequenos não escondam os demais.")

    with c_lado:
        if metrica == "Diagnóstico":
            st.markdown(
                "<div style='font-size:0.9rem;line-height:1.6;margin-bottom:1.2rem'>"
                f"<span style='color:{CORES_DIAG['Expansão acelerada']}'>■</span> <b>Expansão acelerada</b>: 20% maiores "
                "saldos por habitante.<br>"
                f"<span style='color:{CORES_DIAG['Retração']}'>■</span> <b>Retração</b>: 20% menores saldos, com perda "
                "de vagas.<br>"
                f"<span style='color:{CORES_DIAG['Alta rotatividade']}'>■</span> <b>Alta rotatividade</b>: muito movimento "
                "por habitante.<br>"
                f"<span style='color:{CORES_DIAG['Estável']}'>■</span> <b>Estável</b> · "
                f"<span style='color:{CORES_DIAG['Dados insuficientes']};text-shadow:0 0 1px #000'>■</span> "
                "<b>Dados insuficientes</b></div>",
                unsafe_allow_html=True)
        elegiveis = mp[ok]

        def linhas(df: pd.DataFrame) -> str:
            return "\n".join(
                f"- {r.municipio_nome}: {fmt(r.saldo, 0, sinal=True)} ({fmt(r.saldo_10k, 0, sinal=True)}/10 mil)"
                for r in df.itertuples())

        st.markdown("**Maiores altas** (saldo por 10 mil hab.)\n\n" + linhas(elegiveis.nlargest(6, "saldo_10k")))
        st.markdown("**Maiores quedas**\n\n" + linhas(elegiveis.nsmallest(6, "saldo_10k")))

    # --- Município em destaque -----------------------------------------------------------------------
    st.selectbox("Município em destaque", sorted(cod_por_nome), index=None, key="mun_sel_mapa",
                 placeholder="Escolha um município ou clique nele no mapa")
    if st.session_state.get("mun_sel_mapa") in cod_por_nome:
        r = mp[mp["municipio_nome"] == st.session_state["mun_sel_mapa"]].iloc[0]
        if r["movimentos"] == 0:
            st.info(f"{r['municipio_nome']} não tem movimentações neste setor no período.")
        else:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Diagnóstico", r["diag"])
            k2.metric("Saldo (12 meses)", fmt(r["saldo"], 0, sinal=True),
                      help=f"{fmt(r['admissoes'])} admissões e {fmt(r['desligamentos'])} desligamentos.")
            k3.metric("Saldo por 10 mil hab.", fmt(r["saldo_10k"], 1, sinal=True))
            k4.metric("Desligamentos por admissão", r["h_rot"])
            k5.metric("Salário mediano de admissão", r["h_sal"])

    st.subheader("Microrregiões")
    st.dataframe(
        ms.sort_values("saldo_por_10mil", ascending=False)[[
            "microrregiao_nome", "cenario", "admissoes", "desligamentos", "saldo", "saldo_por_10mil",
            "giro_por_10mil", "pct_pedido_desl", "fatores"]],
        hide_index=True, width="stretch",
        column_config={
            "microrregiao_nome": "Microrregião", "cenario": "Cenário", "admissoes": "Admissões",
            "desligamentos": "Desligamentos", "saldo": "Saldo",
            "saldo_por_10mil": st.column_config.NumberColumn("Saldo/10 mil", format="%.1f"),
            "giro_por_10mil": st.column_config.NumberColumn("Movimentos/10 mil", format="%.0f"),
            "pct_pedido_desl": st.column_config.NumberColumn("% saída por pedido", format="percent"),
            "fatores": "Fatores associados",
        },
    )

# =============================================================================
# Setores (CNAE)
# =============================================================================
with aba_setores:
    if not eh_industria:
        st.info("O detalhe por divisão CNAE está disponível para a indústria (seções B a F). "
                "Selecione 'Indústria' ou uma seção industrial no filtro lateral.")
    else:
        est_div = carregar("estado_divisao")
        micro_div = carregar("micro_divisao")
        if setor != IND:
            est_div = est_div[est_div["secao"] == setor]
            micro_div = micro_div[micro_div["secao"] == setor]

        st.subheader("Saldo por divisão CNAE (estado)")
        d = est_div.sort_values("saldo")
        fig = px.bar(d, x="saldo", y="divisao_nome", orientation="h",
                     color=(d["saldo"] > 0).map({True: "Saldo positivo", False: "Saldo negativo"}),
                     color_discrete_map={"Saldo positivo": "#2e7d32", "Saldo negativo": "#c62828"},
                     labels={"saldo": "Saldo (12 meses)", "divisao_nome": "", "color": ""})
        fig.update_layout(height=max(380, 22 * len(d)), margin=dict(l=0, r=0, t=10, b=0), legend_orientation="h")
        st.plotly_chart(fig, width="stretch")

        st.subheader("Detalhe por microrregião")
        micros = sorted(micro_div["microrregiao_nome"].unique())
        micro_sel = st.selectbox("Microrregião", micros, key="micro_div")
        dm = micro_div[(micro_div["microrregiao_nome"] == micro_sel)].sort_values("movimentos", ascending=False)
        dm = dm[dm["movimentos"] >= 50]
        fig = px.bar(
            dm.sort_values("saldo_por_10mil"), x="saldo_por_10mil", y="divisao_nome", orientation="h",
            color="cenario", color_discrete_map=CORES, category_orders={"cenario": ORDEM_CENARIO},
            labels={"saldo_por_10mil": "Saldo por 10 mil habitantes da microrregião", "divisao_nome": "", "cenario": "Cenário"},
            hover_data={"saldo": ":,", "admissoes": ":,", "desligamentos": ":,"},
        )
        fig.update_layout(height=max(320, 26 * len(dm)), margin=dict(l=0, r=0, t=10, b=0), legend_orientation="h")
        st.plotly_chart(fig, width="stretch")
        st.caption("Mostra divisões com ao menos 50 movimentações na microrregião. O cenário compara a "
                   "microrregião com as demais na mesma divisão e só é atribuído com volume suficiente.")

# =============================================================================
# Renda e escolaridade
# =============================================================================
with aba_renda:
    st.subheader("Salário de admissão e saldo de vagas")
    d = ms.dropna(subset=["sal_adm_rel", "saldo_por_10mil"])
    d = d[d["cenario"] != "Volume insuficiente"]
    fig = px.scatter(
        d, x="sal_adm_rel", y="saldo_por_10mil", size="movimentos", color="cenario",
        color_discrete_map=CORES, category_orders={"cenario": ORDEM_CENARIO}, hover_name="microrregiao_nome",
        labels={"sal_adm_rel": "Salário mediano de admissão / mediana estadual do setor",
                "saldo_por_10mil": "Saldo por 10 mil habitantes", "cenario": "Cenário"},
        hover_data={"gap_anos_estudo": ":.2f", "movimentos": ":,"},
    )
    fig.add_vline(x=1, line_dash="dash", line_color="#607d8b")
    fig.add_hline(y=0, line_dash="dash", line_color="#607d8b")
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
    st.caption("À esquerda da linha vertical, a microrregião paga na admissão menos que a mediana estadual do setor. "
               "O tamanho da bolha é o volume de movimentações.")

    col_a, col_b = st.columns(2)
    base = ms[ms["cenario"] != "Volume insuficiente"].sort_values("sal_mediana_adm")
    with col_a:
        st.subheader("Salário: admitidos x desligados")
        longo = base.melt(id_vars="microrregiao_nome", value_vars=["sal_mediana_adm", "sal_mediana_desl"],
                          var_name="grupo", value_name="salario")
        longo["grupo"] = longo["grupo"].map({"sal_mediana_adm": "Admitidos", "sal_mediana_desl": "Desligados"})
        fig = px.bar(longo, x="salario", y="microrregiao_nome", color="grupo", barmode="group", orientation="h",
                     color_discrete_map={"Admitidos": "#1565c0", "Desligados": "#90a4ae"},
                     labels={"salario": "Salário mediano (R$)", "microrregiao_nome": "", "grupo": ""})
        fig.update_layout(height=620, legend_orientation="h", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    with col_b:
        st.subheader("Escolaridade: admitidos x desligados")
        longo = base.melt(id_vars="microrregiao_nome", value_vars=["pct_superior_adm", "pct_superior_desl"],
                          var_name="grupo", value_name="pct")
        longo["grupo"] = longo["grupo"].map({"pct_superior_adm": "Admitidos", "pct_superior_desl": "Desligados"})
        fig = px.bar(longo, x="pct", y="microrregiao_nome", color="grupo", barmode="group", orientation="h",
                     color_discrete_map={"Admitidos": "#1565c0", "Desligados": "#90a4ae"},
                     labels={"pct": "% com superior completo ou mais", "microrregiao_nome": "", "grupo": ""})
        fig.update_xaxes(tickformat=".0%")
        fig.update_layout(height=620, legend_orientation="h", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")

# =============================================================================
# Ocupações (CBO)
# =============================================================================
with aba_cbo:
    if not eh_industria:
        st.info("A análise por macrofamília de CBO está disponível para a indústria (seções B a F).")
    else:
        est_macro = carregar("estado_macrofamilia")
        micro_macro = carregar("micro_macrofamilia")
        fonte = carregar("dim_cbo")["fonte_macrofamilia"].value_counts()
        st.caption("Macrofamílias definidas por " + (
            "IA generativa (CBOs de maior volume) e regra por grupo da CBO (demais)." if "IA" in fonte.index
            else "regra por grupo da CBO 2002. Rode `python cbo.py exportar` para refinar com IA."))

        alvo = st.selectbox("Recorte", ["Estado"] + sorted(micro_macro["microrregiao_nome"].unique()), key="recorte_cbo")
        if alvo == "Estado":
            d = est_macro[est_macro["setor"] == setor]
        else:
            d = micro_macro[(micro_macro["setor"] == setor) & (micro_macro["microrregiao_nome"] == alvo)]
        d = d.sort_values("saldo")
        fig = px.bar(d, x="saldo", y="macrofamilia", orientation="h",
                     color=(d["saldo"] > 0).map({True: "Saldo positivo", False: "Saldo negativo"}),
                     color_discrete_map={"Saldo positivo": "#2e7d32", "Saldo negativo": "#c62828"},
                     labels={"saldo": "Saldo (12 meses)", "macrofamilia": "", "color": ""})
        fig.update_layout(height=500, legend_orientation="h", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(
            d.sort_values("movimentos", ascending=False)[[
                "macrofamilia", "admissoes", "desligamentos", "saldo", "sal_mediana_adm", "anos_estudo_adm",
                "pct_pedido_desl"]],
            hide_index=True, width="stretch",
            column_config={
                "macrofamilia": "Macrofamília", "admissoes": "Admissões", "desligamentos": "Desligamentos",
                "saldo": "Saldo",
                "sal_mediana_adm": st.column_config.NumberColumn("Salário mediano admissão (R$)", format="%.0f"),
                "anos_estudo_adm": st.column_config.NumberColumn("Anos de estudo (aprox.)", format="%.1f"),
                "pct_pedido_desl": st.column_config.NumberColumn("% saída por pedido", format="percent"),
            },
        )

        st.subheader("Mapa de calor: saldo por 10 mil habitantes")
        mapa = micro_macro[(micro_macro["setor"] == setor) & (micro_macro["movimentos"] >= cfg.MIN_MOV_CELULA)]
        if not mapa.empty:
            piv = mapa.pivot_table(index="microrregiao_nome", columns="macrofamilia", values="saldo_por_10mil")
            fig = px.imshow(piv, color_continuous_scale="RdYlGn", color_continuous_midpoint=0, aspect="auto",
                            labels=dict(color="Saldo/10 mil"))
            fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Só aparecem combinações com pelo menos {cfg.MIN_MOV_CELULA} movimentações.")

        st.subheader("Nível de qualificação")
        nivel = carregar("estado_nivel")
        nivel = nivel[nivel["setor"] == setor].sort_values("saldo")
        fig = px.bar(nivel, x="saldo", y="nivel_cbo", orientation="h",
                     labels={"saldo": "Saldo (12 meses)", "nivel_cbo": ""}, text="saldo")
        fig.update_traces(marker_color="#37474f", texttemplate="%{text:+,}")
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")

# =============================================================================
# Perfil
# =============================================================================
with aba_perfil:
    perfil = carregar("perfil")
    perfil = perfil[perfil["setor"] == setor]
    st.caption("Distribuição percentual dentro de cada grupo (admitidos somam 100%, desligados somam 100%).")

    def comparar(coluna: str, titulo: str, ordem: list[str] | None = None):
        g = perfil.groupby(coluna)[["admissoes", "desligamentos"]].sum()
        g = g / g.sum()
        if ordem:
            g = g.reindex([o for o in ordem if o in g.index])
        longo = g.reset_index().melt(id_vars=coluna, var_name="grupo", value_name="pct")
        longo["grupo"] = longo["grupo"].map({"admissoes": "Admitidos", "desligamentos": "Desligados"})
        fig = px.bar(longo, x=coluna, y="pct", color="grupo", barmode="group",
                     color_discrete_map={"Admitidos": "#1565c0", "Desligados": "#90a4ae"},
                     labels={coluna: "", "pct": "% do grupo", "grupo": ""}, title=titulo)
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=360, legend_orientation="h", margin=dict(l=0, r=0, t=40, b=0))
        return fig

    p1, p2 = st.columns(2)
    p1.plotly_chart(comparar("faixa_etaria", "Faixa etária", cfg.FAIXAS_ETARIAS_ROTULOS + ["Não informada"]), width="stretch")
    p2.plotly_chart(comparar("escolaridade_grupo", "Escolaridade", cfg.ESCOLARIDADE_ORDEM + ["Não informada"]), width="stretch")
    st.plotly_chart(comparar("sexo_rotulo", "Sexo"), width="stretch")

# =============================================================================
# Contexto e recomendações
# =============================================================================
with aba_contexto:
    if not cfg.CONTEXTO_JSON.exists():
        st.info(f"Arquivo de contexto não encontrado em `{cfg.CONTEXTO_JSON}`.")
    else:
        ctx = ctxmod.carregar()
        municipio_subclasse_disp = (PASTA / "municipio_subclasse.parquet").exists()

        st.subheader("O que está por trás: contexto estadual")
        cols = st.columns(len(ctx["estado"]))
        for col, card in zip(cols, ctx["estado"]):
            with col:
                st.markdown(f"**{card['tag']}**")
                st.metric(card["titulo"], card["numero"])
                st.caption(card["texto"])
                st.caption(f"Fonte: [{card['fonte']}]({card['url']})")

        st.divider()
        st.subheader("Casos por município: nosso dado x a notícia")
        if not municipio_subclasse_disp:
            st.warning(
                "`municipio_subclasse.parquet` ainda não existe. Rode `python pipeline.py` com o "
                "CAGED completo para calcular o saldo de cada caso (os textos abaixo aparecem sem o número)."
            )
            municipio_subclasse = pd.DataFrame(columns=["municipio_codigo", "subclasse", "saldo"])
        else:
            municipio_subclasse = carregar("municipio_subclasse")

        for caso in ctx["municipios"]:
            dado = ctxmod.nosso_dado_caso(caso, municipio_subclasse, dim_mun)
            with st.container(border=True):
                st.markdown(f"**{caso['tag']}** · {', '.join(caso['municipios'])}")
                st.markdown(f"#### {caso['titulo']}")
                if dado["encontrado"]:
                    st.metric(f"Nosso dado ({caso['rotulo_dado']}, 12 meses)", ctxmod.fmt_saldo(dado["saldo"]))
                else:
                    st.caption(f"Nosso dado ({caso['rotulo_dado']}): não foi possível calcular agora.")
                st.write(caso["texto"])
                if caso["fontes"]:
                    links = " · ".join(f"[{f['nome']}]({f['url']})" for f in caso["fontes"])
                    st.caption(f"Fonte: {links}")
                else:
                    st.caption("Sem notícia encontrada; tratado como \"a investigar\".")

        st.divider()
        st.subheader("O que fazer: recomendações")
        est_div_ctx = carregar("estado_divisao")
        est_escolaridade = carregar("estado_escolaridade") if (PASTA / "estado_escolaridade.parquet").exists() else None
        if est_escolaridade is None:
            st.warning(
                "`estado_escolaridade.parquet` ainda não existe. Rode `python pipeline.py` de novo "
                "(com a tabela nova) para preencher os números de salário por escolaridade nas recomendações."
            )
            placeholders = {}
        else:
            placeholders = ctxmod.calcular_placeholders(
                est_setor, est_div_ctx, est_escolaridade, carregar("municipio_setor"), dim_mun, IND,
            )

        for rec in ctx["recomendacoes"]:
            with st.container(border=True):
                st.markdown(f"#### {rec['titulo']}")
                try:
                    evidencia = rec["evidencia"].format(**placeholders) if placeholders else rec["evidencia"]
                except KeyError:
                    evidencia = rec["evidencia"]
                st.write(f"**Evidência:** {evidencia}")
                try:
                    acao = rec["acao"].format(**placeholders) if placeholders else rec["acao"]
                except KeyError:
                    acao = rec["acao"]
                st.write(f"**Ação:** {acao}")
                st.caption(f"Como medir: {rec['medir']}")

# =============================================================================
# Metodologia
# =============================================================================
with aba_metodo:
    st.markdown(f"""
### Fonte e escopo
- **Novo CAGED (movimentações)** de Santa Catarina, competências **{ini} a {fim}** ({meta['linhas_analisadas']:,} movimentações analisadas).
- **População**: estimativa IBGE 2026 por município, somada por microrregião. Usada nos indicadores "por 10 mil habitantes".
- **Território**: microrregiões do IBGE (API de localidades), ligadas ao CAGED pelos 6 primeiros dígitos do código do município.
- **Indústria**: seções CNAE 2.0 **B, C, D, E e F** (extrativas, transformação, energia, água e resíduos, construção).

### Indicadores
- **Saldo** = admissões - desligamentos. **Saldo por 10 mil hab.** = saldo / população x 10.000.
- **Desligamentos por admissão**: acima de 1, o setor encolhe.
- **Salário**: mediana do campo `salário`, só para unidades de pagamento confiáveis (hora, dia, quinzena, mês), valor > 0 e <= R$ {cfg.SALARIO_MAXIMO:,.0f}.
  Registros sem salário válido continuam nas contagens de saldo.
- **Escolaridade**: % com superior completo ou mais; **anos de estudo** são uma aproximação a partir do grau de instrução.
- **Salário relativo** = mediana de admissão da célula / mediana estadual do mesmo setor.

### Classificação de cenários (ponto de partida, não é modelo estatístico)
Cada microrregião é comparada com as demais **no mesmo setor** (percentis do próprio grupo):
- **Expansão acelerada**: saldo positivo e saldo por 10 mil hab. no quartil superior.
- **Sinal de apagão**: contratações por habitante no quartil superior, saldo abaixo da mediana e saída voluntária acima da mediana (contrata muito e não consegue crescer).
- **Retração**: saldo negativo e saldo por 10 mil hab. no quartil inferior.
- Células com menos de {cfg.MIN_MOV_CELULA} movimentações ficam como "Volume insuficiente".
- **Fatores associados**: salário de admissão abaixo de {cfg.LIM_SALARIO_REL:.0%} da referência estadual, admitidos com {cfg.LIM_GAP_ANOS_ESTUDO} ano ou mais de estudo a mais que os desligados, saída voluntária e término de contrato no quartil superior.

### Limites da análise
- O CAGED cobre **apenas emprego formal**.
- **Sem estoque de empregos** não há taxa de rotatividade real. Usamos admissões e desligamentos por habitante e a parcela de pedidos de demissão.
- **Filtro de exclusões (MOV x EX) não aplicado**: o CSV recebido não traz o indicador de exclusão.
- Praticamente todas as admissões (99,96%) vêm com tipo "ignorado" (código 97), então não separamos primeiro emprego de reemprego.
- Os limiares da classificação são uma convenção da equipe. Os resultados mostram **sinais**, não causalidade.
""")
    st.subheader("Relatório de qualidade dos dados")
    st.dataframe(pd.read_csv(PASTA / "relatorio_qualidade.csv"), hide_index=True, width="stretch")
