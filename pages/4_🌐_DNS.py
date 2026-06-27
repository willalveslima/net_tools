import streamlit as st
import pandas as pd
from datetime import datetime
from net_tools.state import init_state
from net_tools.checks import dns_query_all
from net_tools.utils import normalize_target

init_state()

st.title("🌐 Consulta DNS Avançada")

st.info("Insira um domínio para buscar os registros DNS detalhados (A, AAAA, MX, TXT, CNAME, NS, SOA).")

target = st.text_input(
    "Domínio",
    placeholder="Ex.: google.com, github.com, bb.com.br",
)

if st.button("Executar Consulta", type="primary", use_container_width=True):
    target_clean = normalize_target(target)

    if not target_clean:
        st.warning("Por favor, informe um domínio.")
    else:
        with st.spinner(f"Consultando registros DNS para {target_clean}..."):
            results = dns_query_all(target_clean)

        if "error" in results:
            st.error(results["error"][0].get("Erro", "Erro ao resolver domínio."))
        else:
            st.success("Consulta concluída ✅")

            st.session_state.last_dns_result = {
                "target": target_clean,
                "data": results,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

last_result = st.session_state.get("last_dns_result")

if last_result:
    st.divider()
    st.subheader(f"Registros DNS para `{last_result['target']}`")
    st.caption(f"Consulta realizada em: {last_result['timestamp']}")

    data = last_result["data"]

    consolidated_records = []

    # Identifica quais abas de registros possuem dados
    available_types = [t for t in data if t != "_warning" and t != "error" and data[t]]

    if not available_types:
        st.warning("Nenhum registro DNS encontrado para este domínio.")
    else:
        # Preencher os dados consolidados para exportação
        for rtype, records in data.items():
            if rtype in ("_warning", "error") or not records:
                continue
            for r in records:
                if rtype == "MX":
                    consolidated_records.append({
                        "Tipo": "MX",
                        "Detalhe": f"Pref: {r.get('Preferência')}",
                        "Valor": r.get('Servidor')
                    })
                elif rtype == "SOA":
                    details = f"Serial: {r.get('Serial')}, Refresh: {r.get('Refresh')}, Retry: {r.get('Retry')}"
                    consolidated_records.append({
                        "Tipo": "SOA",
                        "Detalhe": details,
                        "Valor": f"MName: {r.get('MName')}, RName: {r.get('RName')}"
                    })
                else:
                    consolidated_records.append({
                        "Tipo": rtype,
                        "Detalhe": "-",
                        "Valor": r.get('Valor') or r.get('Erro') or ""
                    })

        # Exibir avisos de pacotes ausentes, se houver
        if "_warning" in data:
            st.warning(data["_warning"][0])

        # Cria abas para visualização
        tabs = st.tabs(available_types + ["Todos (Tabela)"])

        for idx, rtype in enumerate(available_types):
            with tabs[idx]:
                df = pd.DataFrame(data[rtype])
                st.dataframe(df, use_container_width=True)

        with tabs[-1]:
            df_all = pd.DataFrame(consolidated_records)
            st.dataframe(df_all, use_container_width=True)

            csv = df_all.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Baixar registros DNS (CSV)",
                csv,
                file_name=f"dns_records_{last_result['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )