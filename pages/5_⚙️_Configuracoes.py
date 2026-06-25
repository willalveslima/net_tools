import streamlit as st

from net_tools.state import init_state

init_state()

st.title("⚙️ Configurações")

config = st.session_state.config

st.subheader("Ping do destino")

config["ping_count"] = st.slider(
    "Pacotes no ping do destino",
    min_value=1,
    max_value=20,
    value=config["ping_count"],
)

st.subheader("MTR-like")

config["mtr_ping_count"] = st.slider(
    "Pacotes por hop no MTR-like",
    min_value=1,
    max_value=20,
    value=config["mtr_ping_count"],
)

config["max_hops"] = st.slider(
    "Máximo de hops no traceroute",
    min_value=5,
    max_value=64,
    value=config["max_hops"],
)

config["resolve_hop_hostnames"] = st.checkbox(
    "Resolver nomes dos hops",
    value=config["resolve_hop_hostnames"],
)

config["reverse_dns_timeout_s"] = st.slider(
    "Timeout DNS reverso dos hops (s)",
    min_value=0.5,
    max_value=10.0,
    value=float(config["reverse_dns_timeout_s"]),
    step=0.5,
)

st.subheader("Timeouts")

config["timeout_ms"] = st.slider(
    "Timeout ICMP por pacote (ms)",
    min_value=500,
    max_value=5000,
    value=config["timeout_ms"],
    step=500,
)

config["tcp_timeout_s"] = st.slider(
    "Timeout TCP por porta (s)",
    min_value=0.5,
    max_value=10.0,
    value=float(config["tcp_timeout_s"]),
    step=0.5,
)

st.subheader("TCP")

config["ports"] = st.text_input(
    "Portas TCP padrão",
    value=config["ports"],
    help="Aceita lista e intervalos. Ex.: 80,443,8000-8010",
)

st.subheader("Execução")

config["max_workers"] = st.slider(
    "Threads paralelas",
    min_value=1,
    max_value=32,
    value=config["max_workers"],
)

st.success("Configuração salva automaticamente ✅")

st.json(config)