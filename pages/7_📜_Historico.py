import json
from datetime import datetime

import pandas as pd
import streamlit as st

from net_tools.state import init_state
from net_tools.db import load_test_history

init_state()

st.title("📜 Histórico de Testes")

df = load_test_history()

if df.empty:
    st.warning("Nenhum teste registrado ainda.")
    st.stop()


# ========= FILTROS =========
st.subheader("Filtros")

col1, col2, col3 = st.columns(3)

with col1:
    filtro_host = st.text_input("Filtrar por Host")

with col2:
    filtro_origem = st.text_input("Filtrar por IP de Origem")

with col3:
    limite = st.slider("Registros", 10, 200, 50)


if filtro_host:
    df = df[df["target"].str.contains(filtro_host, case=False, na=False)]

if filtro_origem:
    df = df[df["origin_ip"].str.contains(filtro_origem, case=False, na=False)]

df = df.head(limite)


# ========= LISTA =========
st.subheader("Lista de testes")

df_view = df.copy()
df_view["timestamp"] = pd.to_datetime(df_view["timestamp"])

cols = [
    "id",
    "timestamp",
    "target",
    "origin_ip",
    "destination_ip",
    "avg_ping",
    "packet_loss",
    "total_hops",
    "open_ports",
]

cols = [c for c in cols if c in df_view.columns]

st.dataframe(
    df_view[cols],
    use_container_width=True,
)


# ========= DETALHE =========
st.divider()
st.subheader("Detalhes do teste")

selected_id = st.selectbox(
    "Selecione um teste",
    df["id"]
)

row = df[df["id"] == selected_id].iloc[0]

result = json.loads(row["raw_json"])


# ========= CONTEXTO =========
st.markdown("### Contexto")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Data", row["timestamp"])

with c2:
    st.metric("Host", row["target"])

with c3:
    st.metric("IP Origem", row["origin_ip"])


# 🔥 NOVO: linha dedicada com origem x destino
c4, c5 = st.columns(2)

with c4:
    st.metric("Origem", row["origin_ip"])

with c5:
    st.metric("Destino", row["destination_ip"])


# ========= MÉTRICAS =========
st.markdown("### Métricas")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Ping médio", row["avg_ping"], "ms")

with m2:
    st.metric("Perda (%)", row["packet_loss"])

with m3:
    st.metric("Hops", row["total_hops"])

with m4:
    st.metric("Portas abertas", row["open_ports"])


# ========= JSON =========
with st.expander("🔍 Ver resultado completo"):
    st.code(json.dumps(result, indent=2, ensure_ascii=False))


# ========= EXPORT =========
csv = df_view.to_csv(index=False).encode("utf-8")

st.download_button(
    "Exportar histórico (CSV)",
    csv,
    file_name=f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
)