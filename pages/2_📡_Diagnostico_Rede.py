import streamlit as st
import pandas as pd

from net_tools.state import init_state
from net_tools.checks import ping_test, traceroute_test

init_state()

st.title("📡 Diagnóstico de Rede")

config = st.session_state.config

target = st.text_input("Host ou IP")

# botão único (UX melhor)
if st.button("Executar diagnóstico", type="primary"):

    if not target:
        st.warning("Informe um host ou IP")
    else:
        progress = st.progress(0)
        status = st.empty()

        # ===== PING =====
        status.write("Executando ping...")
        progress.progress(0.3)

        ping = ping_test(
            target,
            count=config["ping_count"],
            timeout_ms=config["timeout_ms"]
        )

        # ===== TRACEROUTE =====
        status.write("Executando traceroute...")
        progress.progress(0.7)

        trace = traceroute_test(
            target,
            max_hops=config["max_hops"],
            resolve_names=config["resolve_hop_hostnames"],
            reverse_dns_timeout_s=config["reverse_dns_timeout_s"],
            max_workers=config["max_workers"]
        )

        progress.progress(1.0)
        status.success("Concluído ✅")

        # ===== OUTPUT =====
        tab_ping, tab_trace = st.tabs(["Ping", "Traceroute"])

        with tab_ping:
            st.json(ping.get("summary", {}))
            st.code(ping.get("stdout", ""), language="text")

        with tab_trace:
            hops = trace.get("hops", [])

            if hops:
                df = pd.DataFrame(hops)
                st.dataframe(df[["hop","ip","hostname"]], use_container_width=True)

            st.code(trace.get("stdout", ""), language="text")
