import streamlit as st


DEFAULT_CONFIG = {
    "ping_count": 4,
    "mtr_ping_count": 3,
    "timeout_ms": 1000,
    "max_workers": 8,
    "ports": "22,53,80,443,445,1433,1521,3389,8080,8443",
    "max_hops": 30,
    "reverse_dns_timeout_s": 2.0,
    "tcp_timeout_s": 2.0,
    "resolve_hop_hostnames": True,
}


def init_state():
    """
    Inicializa e atualiza o estado global da aplicação.

    Mesmo que a config já exista, garante que novas chaves sejam adicionadas
    sem quebrar páginas antigas.
    """
    if "config" not in st.session_state:
        st.session_state.config = DEFAULT_CONFIG.copy()
    else:
        for key, value in DEFAULT_CONFIG.items():
            if key not in st.session_state.config:
                st.session_state.config[key] = value