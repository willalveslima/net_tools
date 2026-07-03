from datetime import datetime

import pandas as pd
import streamlit as st

from net_tools.checks import mtr_like_test, traceroute_test
from net_tools.state import init_state
from net_tools.utils import normalize_target

init_state()

st.title("📊 MTR-like")

config = st.session_state.config

target = st.text_input(
    "Host ou IP",
    placeholder="Ex.: www.bb.com.br, servidor.interno.local ou 8.8.8.8",
)

if st.button("Executar MTR-like", type="primary", use_container_width=True):
    target_clean = normalize_target(target)

    if not target_clean:
        st.warning("Informe um host ou IP.")
    else:
        progress_bar = st.progress(0)
        status = st.empty()

        def update_progress(current: int, total: int, message: str):
            progress_bar.progress(min(1.0, current / max(total, 1)))
            status.write(f"⏳ {message} ({current}/{total})")

        status.write("Executando traceroute para descobrir hops...")

        trace = traceroute_test(
            target_clean,
            max_hops=config["max_hops"],
            resolve_names=config["resolve_hop_hostnames"],
            reverse_dns_timeout_s=config["reverse_dns_timeout_s"],
            max_workers=config["max_workers"],
            timeout_ms=config["timeout_ms"]
        )

        hops = trace.get("hops", [])

        if not hops:
            st.warning("Nenhum hop com IP foi identificado.")
        else:
            st.subheader("Hops detectados")
            df_hops = pd.DataFrame(hops)
            hop_cols = ["hop", "ip", "hostname", "raw"]
            hop_cols = [c for c in hop_cols if c in df_hops.columns]
            st.dataframe(df_hops[hop_cols], use_container_width=True)

            st.subheader("Resultado MTR-like")

            mtr = mtr_like_test(
                hops,
                count_per_hop=config["mtr_ping_count"],
                timeout_ms=config["timeout_ms"],
                max_workers=config["max_workers"],
                progress_callback=update_progress,
            )

            progress_bar.progress(1.0)
            status.success("MTR-like concluído ✅")

            if mtr:
                df_mtr = pd.DataFrame(mtr)

                cols = [
                    "hop",
                    "ip",
                    "hostname",
                    "packet_loss_percent",
                    "min_ms",
                    "avg_ms",
                    "max_ms",
                    "timeout",
                ]

                cols = [c for c in cols if c in df_mtr.columns]

                st.dataframe(df_mtr[cols], use_container_width=True)

                csv = df_mtr[cols].to_csv(index=False).encode("utf-8")

                st.download_button(
                    "Baixar CSV do MTR-like",
                    csv,
                    file_name=f"net_tools_mtr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

            with st.expander("Saída bruta do traceroute"):
                st.code(trace.get("stdout", ""), language="text")