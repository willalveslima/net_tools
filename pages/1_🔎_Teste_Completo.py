import json
from datetime import datetime

import pandas as pd
import streamlit as st

from net_tools.state import init_state
from net_tools.checks import run_all_tests
from net_tools.utils import normalize_target, parse_ports
from net_tools.db import save_test_result

init_state()

st.title("🔎 Teste Completo")

config = st.session_state.config

target = st.text_input(
    "Domínio ou IP",
    placeholder="Ex.: www.bb.com.br, servidor.local ou 8.8.8.8",
)


# ========= AUX =========
def get_destination_ips(result):
    if result.get("is_ip"):
        return result.get("target")

    dns = result.get("dns", {})
    ips = dns.get("addresses") or []

    if not ips:
        return "N/D"

    return ", ".join(ips)


def color_mtr(val, tipo):
    if val is None or pd.isna(val):
        return "color: gray"

    if tipo == "loss":
        if val > 0:
            return "color: red; font-weight: bold"
        return "color: green"

    if tipo == "lat":
        if val >= 80:
            return "color: red; font-weight: bold"
        elif val >= 20:
            return "color: orange"
        else:
            return "color: green"

    return ""


# ========= EXECUÇÃO =========
if st.button("Executar testes", type="primary", use_container_width=True):

    target_clean = normalize_target(target)
    ports = parse_ports(config["ports"])

    if not target_clean:
        st.warning("Informe um domínio ou IP")
    else:
        bar = st.progress(0)
        status = st.empty()

        def progress(step, total, msg):
            bar.progress(step / total)
            status.write(f"⏳ {msg} ({step}/{total})")

        result = run_all_tests(
            target_clean,
            tcp_ports=ports,
            ping_count=config["ping_count"],
            mtr_ping_count=config["mtr_ping_count"],
            timeout_ms=config["timeout_ms"],
            tcp_timeout_s=config["tcp_timeout_s"],
            reverse_dns_timeout_s=config["reverse_dns_timeout_s"],
            max_hops=config["max_hops"],
            max_workers=config["max_workers"],
            resolve_hop_hostnames=config["resolve_hop_hostnames"],
            progress_callback=progress,
        )

        bar.progress(1.0)
        status.success("✅ Concluído")

        st.session_state.result = result
        save_test_result(result)


# ========= RESULTADO =========
result = st.session_state.get("result")


if result:

    st.divider()

    origin_ip = result.get("origin_ip") or "N/D"
    destination_ip = get_destination_ips(result)

    # ✅ CONTEXTO
    c1, c2 = st.columns(2)

    with c1:
        st.metric("IP Origem", origin_ip)

    with c2:
        st.metric("IP Destino", destination_ip)

    st.subheader(f"Resultado: {result['target']}")

    dns = result.get("dns")
    ping = result.get("ping", {})
    hops = result.get("hops", [])
    mtr = result.get("mtr", [])
    tcp = result.get("tcp", [])

    ping_summary = ping.get("summary", {})

    open_ports = [p["port"] for p in tcp if p.get("open")]
    named_hops = sum(1 for h in hops if h.get("hostname"))

    # ========= MÉTRICAS =========
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("DNS", "OK" if dns and dns.get("success") else "Falha")

    with col2:
        st.metric(
            "Ping médio",
            ping_summary.get("avg_ms") or "N/D",
            "ms"
        )

    with col3:
        st.metric("Hops", len(hops), f"{named_hops} com nome")

    with col4:
        st.metric("Portas abertas", len(open_ports))

    # ========= ABAS =========
    tab_dns, tab_ping, tab_trace, tab_mtr, tab_tcp, tab_json = st.tabs(
        ["DNS", "Ping", "Traceroute", "MTR", "TCP", "JSON"]
    )

    # DNS
    with tab_dns:
        st.json(dns)

    # PING
    with tab_ping:
        st.json(ping_summary)
        st.code(ping.get("stdout", ""))

    # TRACEROUTE
    with tab_trace:
        if hops:
            df = pd.DataFrame(hops)
            st.dataframe(df[["hop","ip","hostname"]], use_container_width=True)
        st.code(result.get("traceroute", {}).get("stdout",""))

    # ========= MTR =========
    with tab_mtr:
        if mtr:

            df = pd.DataFrame(mtr)

            cols = [
                "hop",
                "ip",
                "hostname",
                "packet_loss_percent",
                "min_ms",
                "avg_ms",
                "max_ms"
            ]

            df_view = df[cols]

            styled = df_view.style \
                .applymap(lambda v: color_mtr(v, "lat"), subset=["min_ms","avg_ms","max_ms"]) \
                .applymap(lambda v: color_mtr(v, "loss"), subset=["packet_loss_percent"])

            st.dataframe(styled, use_container_width=True)

            # export
            csv = df_view.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Exportar CSV MTR",
                csv,
                f"mtr_{datetime.now().strftime('%H%M%S')}.csv"
            )
        else:
            st.warning("Sem dados de MTR")

    # TCP
    with tab_tcp:
        if tcp:
            df = pd.DataFrame(tcp)
            st.dataframe(df, use_container_width=True)

            if open_ports:
                st.success(f"Abertas: {open_ports}")
        else:
            st.info("Sem dados TCP")

    # JSON
    with tab_json:
        st.code(json.dumps(result, indent=2, ensure_ascii=False))