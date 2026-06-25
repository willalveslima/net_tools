from datetime import datetime

import pandas as pd
import streamlit as st

from net_tools.checks import tcp_port_test
from net_tools.state import init_state
from net_tools.utils import normalize_target, parse_ports

init_state()

st.title("🔐 Checagem de Portas TCP")

config = st.session_state.config

TCP_SERVICE_OPTIONS = {
    "FTP - 21": 21,
    "SSH - 22": 22,
    "TELNET - 23": 23,
    "SMTP - 25": 25,
    "DNS - 53": 53,
    "HTTP - 80": 80,
    "POP3 - 110": 110,
    "NTP - 123": 123,
    "MS-RPC - 135": 135,
    "NETBIOS - 139": 139,
    "IMAP - 143": 143,
    "LDAP - 389": 389,
    "HTTPS - 443": 443,
    "SMB - 445": 445,
    "SMTPS - 465": 465,
    "SMTP Submission - 587": 587,
    "LDAPS - 636": 636,
    "IMAPS - 993": 993,
    "POP3S - 995": 995,
    "MSSQL - 1433": 1433,
    "Oracle - 1521": 1521,
    "MySQL - 3306": 3306,
    "RDP - 3389": 3389,
    "PostgreSQL - 5432": 5432,
    "VNC - 5900": 5900,
    "HTTP Alt - 8080": 8080,
    "HTTPS Alt - 8443": 8443,
}

st.info(
    "Selecione serviços TCP comuns e/ou informe portas adicionais. "
    "As portas adicionais aceitam lista e intervalos, por exemplo: "
    "`8443,9000-9010,10050`."
)

target = st.text_input(
    "Host ou IP",
    placeholder="Ex.: servidor.interno.local, www.bb.com.br ou 8.8.8.8",
)

st.subheader("Serviços TCP comuns")

default_selected = [
    "SSH - 22",
    "DNS - 53",
    "HTTP - 80",
    "HTTPS - 443",
    "SMB - 445",
    "MSSQL - 1433",
    "Oracle - 1521",
    "RDP - 3389",
]

selected_services = st.multiselect(
    "Selecione os serviços para testar",
    options=list(TCP_SERVICE_OPTIONS.keys()),
    default=[item for item in default_selected if item in TCP_SERVICE_OPTIONS],
)

st.subheader("Portas adicionais")

extra_ports_input = st.text_input(
    "Portas TCP adicionais",
    value=config.get("ports", ""),
    help="Aceita lista e intervalos. Ex.: 80,443,8000-8010",
)

col1, col2, col3 = st.columns(3)

with col1:
    tcp_timeout_s = st.number_input(
        "Timeout TCP por porta (s)",
        min_value=0.5,
        max_value=30.0,
        value=float(config.get("tcp_timeout_s", 2.0)),
        step=0.5,
    )

with col2:
    max_workers = st.number_input(
        "Threads paralelas",
        min_value=1,
        max_value=64,
        value=int(config.get("max_workers", 8)),
        step=1,
    )

with col3:
    mostrar_fechadas = st.checkbox(
        "Mostrar portas fechadas/filtradas",
        value=True,
    )

if st.button("Executar checagem TCP", type="primary", use_container_width=True):
    target_clean = normalize_target(target)

    if not target_clean:
        st.warning("Informe um host ou IP para iniciar o teste.")
    else:
        service_ports = [
            TCP_SERVICE_OPTIONS[item]
            for item in selected_services
            if item in TCP_SERVICE_OPTIONS
        ]

        extra_ports = parse_ports(extra_ports_input)

        ports = sorted(set(service_ports + extra_ports))

        if not ports:
            st.warning("Selecione ao menos um serviço TCP ou informe portas adicionais.")
        else:
            progress_bar = st.progress(0)
            status = st.empty()

            def update_progress(current: int, total: int, message: str):
                progress_bar.progress(min(1.0, current / max(total, 1)))
                status.write(f"⏳ {message} ({current}/{total})")

            result = tcp_port_test(
                target_clean,
                ports=ports,
                timeout=tcp_timeout_s,
                max_workers=max_workers,
                progress_callback=update_progress,
            )

            progress_bar.progress(1.0)
            status.success("Checagem TCP concluída ✅")

            st.session_state.last_tcp_result = {
                "target": target_clean,
                "ports": ports,
                "result": result,
            }

last_tcp = st.session_state.get("last_tcp_result")

if last_tcp:
    st.divider()
    st.subheader(f"Resultado TCP para: `{last_tcp['target']}`")

    result = last_tcp["result"]

    if result:
        df = pd.DataFrame(result)

        open_ports = df[df["open"] == True]["port"].tolist()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Portas testadas", len(df))

        with col2:
            st.metric("Portas abertas", len(open_ports))

        with col3:
            st.metric("Portas fechadas/filtradas", len(df) - len(open_ports))

        if open_ports:
            st.success(f"Portas abertas: {open_ports}")
        else:
            st.warning("Nenhuma porta aberta detectada nas portas testadas.")

        if not mostrar_fechadas:
            df = df[df["open"] == True]

        visible_cols = [
            "port",
            "service",
            "status",
            "open",
            "elapsed_ms",
            "error",
        ]

        visible_cols = [col for col in visible_cols if col in df.columns]

        st.dataframe(
            df[visible_cols],
            use_container_width=True,
        )

        csv = df[visible_cols].to_csv(index=False).encode("utf-8")

        st.download_button(
            "Baixar CSV do teste TCP",
            csv,
            file_name=f"net_tools_tcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

        with st.expander("JSON completo"):
            st.json(last_tcp)

    else:
        st.warning("Nenhum resultado TCP disponível.")