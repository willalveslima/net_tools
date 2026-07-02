import pandas as pd
import streamlit as st
import datetime
import ipaddress

from net_tools.state import init_state
from net_tools.checks import subnet_scan_test
from net_tools.db import (
    save_subnet,
    delete_subnet,
    list_subnets,
    save_subnet_scan,
    get_last_subnet_scan
)

# Inicializa o estado global da aplicação
init_state()

st.set_page_config(
    page_title="Varredura de Subrede",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌐 Varredura de Subrede (ICMP)")
st.markdown(
    "Esta ferramenta realiza varreduras rápidas em lote via pacotes PING (ICMP) "
    "para identificar hosts respondendo em uma determinada subrede local, permitindo comparar resultados "
    "com a varredura anterior para identificar quedas ou novos dispositivos na rede."
)

# ================= SIDEBAR: GERENCIAMENTO DE SUBREDES =================
st.sidebar.header("📁 Gerenciar Subredes")

# 1. Cadastrar Subrede
with st.sidebar.expander("➕ Cadastrar Nova Subrede", expanded=False):
    subnet_name = st.text_input("Nome Amigável", placeholder="Ex: WiFi Escritório")
    subnet_cidr = st.text_input("Faixa CIDR", placeholder="Ex: 192.168.1.0/24")
    
    if st.button("Salvar Subrede", type="primary", use_container_width=True):
        if not subnet_name or not subnet_cidr:
            st.error("Informe o nome e a faixa CIDR!")
        else:
            try:
                # Validar CIDR
                net = ipaddress.ip_network(subnet_cidr.strip(), strict=False)
                
                # Restringir tamanho para performance no Windows
                if net.prefixlen < 24:
                    st.error("Máscara deve ser no mínimo /24 (máx 256 IPs) para evitar sobrecarga do SO.")
                else:
                    save_subnet(subnet_name, subnet_cidr)
                    st.success("Subrede cadastrada com sucesso!")
                    st.rerun()
            except ValueError:
                st.error("Faixa CIDR inválida! Use o formato correto (ex: 192.168.1.0/24).")

# 2. Listar e Excluir Subrede
subnets_list = list_subnets()

if subnets_list:
    st.sidebar.divider()
    st.sidebar.subheader("🗑️ Excluir Subredes")
    
    # Lista de subredes para exclusão
    subnet_to_del = st.sidebar.selectbox(
        "Selecione uma subrede para remover",
        options=subnets_list,
        format_func=lambda x: f"{x['name']} ({x['cidr']})"
    )
    
    confirm_del = st.sidebar.checkbox("Confirmar remoção permanente")
    if st.sidebar.button("Excluir Subrede", type="secondary", disabled=not confirm_del, use_container_width=True):
        delete_subnet(subnet_to_del["id"])
        st.sidebar.success("Subrede excluída com sucesso!")
        st.rerun()
else:
    st.sidebar.info("Nenhuma subrede cadastrada. Cadastre uma acima.")


# ================= TELA PRINCIPAL: EXECUÇÃO DE SCAN =================
if not subnets_list:
    st.info(
        """
        ### ℹ️ Comece cadastrando uma Subrede
        Use o menu lateral esquerdo em **Cadastrar Nova Subrede** para registrar as redes que deseja escanear.
        
        *Exemplo comum:*
        * **Nome:** Rede Local
        * **Faixa CIDR:** `192.168.1.0/24` (ou a faixa correspondente ao gateway de sua rede)
        """
    )
else:
    st.subheader("Configurações do Scan")
    
    # Seleção de Subrede para varredura
    selected_subnet = st.selectbox(
        "Selecione a Subrede de Destino",
        options=subnets_list,
        format_func=lambda x: f"{x['name']} — {x['cidr']}"
    )
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        timeout = st.slider("Timeout do PING (ms)", min_value=100, max_value=1000, value=300, step=50,
                            help="Valores baixos tornam o teste mais rápido, mas podem ignorar conexões com latência instável.")
    with col_opt2:
        threads = st.slider("Lote de threads simultâneas", min_value=10, max_value=100, value=50, step=5,
                            help="Controla o paralelismo dos processos de ping do Windows. Padrão: 50.")

    # Inicializa sessão para guardar resultados do último scan executado nesta sessão
    if "last_sweep_result" not in st.session_state:
        st.session_state.last_sweep_result = None

    if st.button("🚀 Iniciar Varredura de Rede", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total, message):
            progress_bar.progress(current / total)
            status_text.text(f"⏳ {message} ({current}/{total} hosts verificados)")
            
        cidr = selected_subnet["cidr"]
        subnet_id = selected_subnet["id"]
        
        # Buscar o teste mais recente antes de salvar o novo scan
        last_scan_data = get_last_subnet_scan(subnet_id)
        
        # Executar scan
        try:
            active_hosts = subnet_scan_test(
                cidr=cidr,
                timeout_ms=timeout,
                max_workers=threads,
                progress_callback=update_progress
            )
            
            progress_bar.progress(1.0)
            status_text.success("Varredura concluída com sucesso! ✅")
            
            # Persistir novo scan no SQLite
            save_subnet_scan(subnet_id, active_hosts)
            
            # Comparação (Delta Engine)
            lost_hosts = []
            new_hosts = []
            
            if last_scan_data:
                previous_hosts = last_scan_data.get("active_hosts", [])
                
                # Mapeamento para comparação rápida por IP
                current_ips = {h["ip"] for h in active_hosts}
                previous_ips = {h["ip"] for h in previous_hosts}
                
                # Identifica offline (estavam antes, mas não agora)
                lost_ips = previous_ips - current_ips
                for ip in lost_ips:
                    # Recupera o hostname do registro antigo para exibição amigável
                    old_host = next((h for h in previous_hosts if h["ip"] == ip), {})
                    lost_hosts.append({
                        "ip": ip,
                        "hostname": old_host.get("hostname", ""),
                        "last_seen_latency_ms": old_host.get("latency_ms", 0.0)
                    })
                    
                # Identifica novos (estão agora, mas não antes)
                new_ips = current_ips - previous_ips
                for ip in new_ips:
                    new_host = next((h for h in active_hosts if h["ip"] == ip), {})
                    new_hosts.append(new_host)
            
            # Salvar no session state
            st.session_state.last_sweep_result = {
                "subnet_id": subnet_id,
                "subnet_name": selected_subnet["name"],
                "cidr": cidr,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_hosts": active_hosts,
                "lost_hosts": lost_hosts,
                "new_hosts": new_hosts,
                "has_previous": last_scan_data is not None,
                "previous_timestamp": last_scan_data["timestamp"] if last_scan_data else None
            }
            
        except Exception as e:
            st.error(f"Erro na varredura: {e}")

    # Exibição dos Resultados
    res = st.session_state.last_sweep_result
    
    # Garante que mostra o resultado apenas da subrede atualmente selecionada
    if res and res["subnet_id"] == selected_subnet["id"]:
        st.divider()
        st.subheader(f"Resultados para a subrede: `{res['subnet_name']}` ({res['cidr']})")
        st.caption(f"Varredura executada em: {res['timestamp']}")
        
        # Colunas com Métricas
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Hosts Ativos Atuais", len(res["active_hosts"]))
        with m2:
            if res["has_previous"]:
                st.metric("Hosts Perdidos (Offline)", len(res["lost_hosts"]), delta=-len(res["lost_hosts"]), delta_color="inverse")
            else:
                st.metric("Hosts Perdidos (Offline)", "N/D", help="Necessita de um scan anterior para comparação.")
        with m3:
            if res["has_previous"]:
                st.metric("Novos Hosts Detectados", len(res["new_hosts"]), delta=len(res["new_hosts"]))
            else:
                st.metric("Novos Hosts Detectados", "N/D", help="Necessita de um scan anterior para comparação.")

        # ABAS DE DETALHAMENTO
        tab_active, tab_lost, tab_new = st.tabs([
            "🟢 Ativos no Teste Atual",
            "🔴 Perdidos / Offline",
            "🔵 Novos Detectados"
        ])
        
        with tab_active:
            if not res["active_hosts"]:
                st.warning("Nenhum host respondeu aos pacotes PING nesta subrede.")
            else:
                df_active = pd.DataFrame(res["active_hosts"])
                df_active = df_active[["ip", "hostname", "latency_ms"]]
                df_active.columns = ["Endereço IP", "Nome do Host (Reverse DNS)", "Latência Média (ms)"]
                st.dataframe(df_active, use_container_width=True)
                
                # Exportar CSV
                csv_active = df_active.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Baixar Lista de Hosts Ativos (CSV)",
                    csv_active,
                    f"hosts_ativos_{res['subnet_name'].replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
        with tab_lost:
            if not res["has_previous"]:
                st.info("Este foi o primeiro scan registrado para esta subrede. Sem dados de comparação anteriores.")
            elif not res["lost_hosts"]:
                st.success("Excelente! Nenhum host ficou offline em relação à varredura anterior.")
            else:
                st.error("Os seguintes hosts responderam na varredura anterior (em {}) mas estão offline agora:".format(res["previous_timestamp"]))
                df_lost = pd.DataFrame(res["lost_hosts"])
                df_lost = df_lost[["ip", "hostname", "last_seen_latency_ms"]]
                df_lost.columns = ["Endereço IP", "Nome do Host (Histórico)", "Última Latência (ms)"]
                st.dataframe(df_lost, use_container_width=True)
                
                # Exportar CSV
                csv_lost = df_lost.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Baixar Lista de Hosts Perdidos (CSV)",
                    csv_lost,
                    f"hosts_perdidos_{res['subnet_name'].replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
        with tab_new:
            if not res["has_previous"]:
                st.info("Este foi o primeiro scan registrado para esta subrede. Sem dados de comparação anteriores.")
            elif not res["new_hosts"]:
                st.info("Nenhum novo dispositivo foi detectado na subrede em relação à varredura anterior.")
            else:
                st.info("Novos hosts identificados respondendo a ping (não listados na varredura anterior de {}):".format(res["previous_timestamp"]))
                df_new = pd.DataFrame(res["new_hosts"])
                df_new = df_new[["ip", "hostname", "latency_ms"]]
                df_new.columns = ["Endereço IP", "Nome do Host (Reverse DNS)", "Latência (ms)"]
                st.dataframe(df_new, use_container_width=True)
                
                # Exportar CSV
                csv_new = df_new.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Baixar Lista de Novos Hosts (CSV)",
                    csv_new,
                    f"hosts_novos_{res['subnet_name'].replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
