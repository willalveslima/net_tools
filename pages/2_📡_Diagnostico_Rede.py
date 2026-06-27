import streamlit as st
import pandas as pd
from datetime import datetime

from net_tools.state import init_state
from net_tools.checks import ping_test, traceroute_test
from net_tools.utils import normalize_target

init_state()

st.title("📡 Diagnóstico de Rede")

config = st.session_state.config

target = st.text_input(
    "Host ou IP",
    placeholder="Ex.: www.google.com ou 8.8.8.8"
)

# Execução
if st.button("Executar diagnóstico", type="primary", use_container_width=True):
    target_clean = normalize_target(target)

    if not target_clean:
        st.warning("Informe um host ou IP")
    else:
        progress = st.progress(0)
        status = st.empty()

        # ===== PING =====
        status.write("Executando ping...")
        progress.progress(0.3)

        ping = ping_test(
            target_clean,
            count=config["ping_count"],
            timeout_ms=config["timeout_ms"]
        )

        # ===== TRACEROUTE =====
        status.write("Executando traceroute...")
        progress.progress(0.7)

        trace = traceroute_test(
            target_clean,
            max_hops=config["max_hops"],
            resolve_names=config["resolve_hop_hostnames"],
            reverse_dns_timeout_s=config["reverse_dns_timeout_s"],
            max_workers=config["max_workers"]
        )

        progress.progress(1.0)
        status.success("Concluído ✅")

        # Salva no Session State para persistir entre re-runs do download
        st.session_state.last_diagnostic = {
            "target": target_clean,
            "ping": ping,
            "trace": trace,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

# Exibição (persistida em Session State)
last_diag = st.session_state.get("last_diagnostic")

if last_diag:
    st.divider()
    st.subheader(f"Resultados para `{last_diag['target']}`")
    st.caption(f"Executado em: {last_diag['timestamp']}")

    ping = last_diag["ping"]
    trace = last_diag["trace"]

    tab_ping, tab_trace = st.tabs(["Ping", "Traceroute"])

    with tab_ping:
        st.markdown("### Resumo do Ping")
        st.json(ping.get("summary", {}))

        st.markdown("### Saída Bruta")
        st.code(ping.get("stdout", ""), language="text")

        ping_raw = ping.get("stdout", "")
        if ping_raw:
            st.download_button(
                "Baixar saída do Ping (TXT)",
                ping_raw,
                file_name=f"ping_{last_diag['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )

    with tab_trace:
        hops = trace.get("hops", [])

        if hops:
            st.markdown("### Tabela de Hops")
            df = pd.DataFrame(hops)
            df_view = df[["hop", "ip", "hostname"]]
            st.dataframe(df_view, use_container_width=True)

            csv = df_view.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Baixar tabela do Traceroute (CSV)",
                csv,
                file_name=f"traceroute_{last_diag['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.markdown("### Saída Bruta")
        st.code(trace.get("stdout", ""), language="text")
