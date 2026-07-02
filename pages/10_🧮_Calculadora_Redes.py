import json
import math
import ipaddress
import pandas as pd
import streamlit as st

# Inicializa o estado global da aplicação
from net_tools.state import init_state
init_state()

st.set_page_config(
    page_title="Calculadora Avançada de Redes",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🧮 Calculadora Avançada de Redes")
st.markdown(
    "Utilitário de apoio para engenharia e planejamento de redes, focado em "
    "cálculos de subredes IPv4/IPv6, alocação dinâmica VLSM e sumarização de rotas."
)

# Helpers e Lógica de Cálculo

def ip_to_binary(ip_obj) -> str:
    """Retorna o IP formatado como octetos binários separados por pontos."""
    if isinstance(ip_obj, (ipaddress.IPv4Address, ipaddress.IPv4Network)):
        if isinstance(ip_obj, ipaddress.IPv4Network):
            ip_addr = ip_obj.network_address
        else:
            ip_addr = ip_obj
        octets = str(ip_addr).split('.')
        return ".".join(f"{int(o):08b}" for o in octets)
    return ""

def get_ipv4_class(ip_str: str) -> str:
    """Retorna a classe tradicional da rede IPv4 baseada no primeiro octeto."""
    try:
        first_octet = int(ip_str.split('.')[0])
        if 1 <= first_octet <= 126:
            return "Classe A"
        elif first_octet == 127:
            return "Classe A (Loopback)"
        elif 128 <= first_octet <= 191:
            return "Classe B"
        elif 192 <= first_octet <= 223:
            return "Classe C"
        elif 224 <= first_octet <= 239:
            return "Classe D (Multicast)"
        elif 240 <= first_octet <= 255:
            return "Classe E (Experimental)"
    except Exception:
        pass
    return "N/D"

def get_ipv6_scope_label(ip_obj: ipaddress.IPv6Address) -> str:
    """Classifica o escopo e tipo do endereço IPv6."""
    if ip_obj.is_loopback:
        return "Loopback (::1)"
    elif ip_obj.is_multicast:
        return "Multicast"
    elif ip_obj.is_link_local:
        return "Unicast Link-Local (fe80::/10)"
    elif ip_obj.is_site_local:
        return "Unicast Site-Local (antigo)"
    elif str(ip_obj).lower().startswith("fc00") or str(ip_obj).lower().startswith("fd00"):
        return "Unique Local (ULA - fc00::/7)"
    elif ip_obj.is_reserved:
        return "Reservado"
    else:
        return "Global Unicast (Público)"

# --- ABAS ---
tab_ipv4, tab_vlsm, tab_sum, tab_ipv6 = st.tabs([
    "🎨 Calculadora IPv4",
    "📊 Divisão VLSM",
    "🧩 Sumarização de Rotas",
    "🌐 Planejamento IPv6"
])

# ================= TAB 1: CALCULADORA IPV4 =================
with tab_ipv4:
    st.header("Análise e Conversão IPv4")
    
    col_ip1, col_ip2 = st.columns([3, 1])
    with col_ip1:
        ipv4_input = st.text_input("Endereço IP", value="192.168.1.135", placeholder="Ex: 10.0.0.1")
    with col_ip2:
        # Gerar opções CIDR
        cidr_options = [f"/{i} — {ipaddress.IPv4Network(f'0.0.0.0/{i}').netmask}" for i in range(33)]
        cidr_select = st.selectbox("Máscara de Rede", options=cidr_options, index=24)
        prefix_len = int(cidr_select.split(" — ")[0].replace("/", ""))

    # Executar cálculos
    try:
        ip_addr = ipaddress.IPv4Address(ipv4_input.strip())
        net = ipaddress.IPv4Network(f"{ipv4_input.strip()}/{prefix_len}", strict=False)
        
        # Obter estatísticas
        net_cidr = net.with_prefixlen
        net_mask = str(net.netmask)
        wildcard = str(net.hostmask)
        network_address = str(net.network_address)
        broadcast = str(net.broadcast_address)
        
        # Calcular hosts válidos
        if prefix_len == 32:
            first_host = str(net.network_address)
            last_host = str(net.network_address)
            usable_hosts = 1
        elif prefix_len == 31:
            first_host = str(net.network_address)
            last_host = str(net.broadcast_address)
            usable_hosts = 2
        else:
            first_host = str(net.network_address + 1)
            last_host = str(net.broadcast_address - 1)
            usable_hosts = net.num_addresses - 2
            
        ip_class = get_ipv4_class(ipv4_input.strip())
        scope = "Privado" if net.is_private else "Público / Internet"
        
        # Mostrar métricas principais
        st.divider()
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Rede CIDR", net_cidr)
            st.metric("Primeiro Host Utilizável", first_host)
        with m_col2:
            st.metric("Máscara Decimal", net_mask)
            st.metric("Último Host Utilizável", last_host)
        with m_col3:
            st.metric("Mascara Wildcard", wildcard)
            st.metric("Broadcast", broadcast)
        with m_col4:
            st.metric("Hosts Utilizáveis", f"{usable_hosts:,}")
            st.metric("Classe / Escopo", f"{ip_class} ({scope})")

        # Exibição Binária Alinhada
        st.subheader("Visualização Binária")
        
        binary_ip = ip_to_binary(ip_addr)
        binary_mask = ip_to_binary(net.netmask)
        binary_net = ip_to_binary(net.network_address)
        binary_brd = ip_to_binary(net.broadcast_address)
        
        # Calcular largura das strings para alinhamento
        code_block = f"""
IP:        {ipv4_input:<15} -> {binary_ip}
Máscara:   {net_mask:<15} -> {binary_mask}
Rede:      {network_address:<15} -> {binary_net}
Broadcast: {broadcast:<15} -> {binary_brd}
        """
        st.code(code_block, language="text")

    except ValueError as e:
        st.error(f"Erro de validação: {e}. Digite um endereço IPv4 válido.")

# ================= TAB 2: DIVISÃO VLSM =================
with tab_vlsm:
    st.header("Planejamento de Subredes VLSM")
    st.markdown(
        "A técnica VLSM (Variable Length Subnet Masking) divide uma rede principal em subredes "
        "com tamanhos de bloco otimizados de acordo com a necessidade exata de hosts de cada segmento."
    )
    
    col_v1, col_v2 = st.columns([2, 3])
    
    with col_v1:
        st.subheader("Configuração da Rede Base")
        vlsm_base_input = st.text_input("Rede Base (CIDR)", value="192.168.0.0/24")
        
        st.subheader("Subredes e Demandas de Hosts")
        st.markdown("Insira os nomes e as demandas de hosts abaixo. Adicione ou remova linhas conforme necessário.")
        
        # Tabela editável dinâmica para as demandas
        default_demands = pd.DataFrame([
            {"Subrede": "LAN Diretoria", "Hosts Requeridos": 60},
            {"Subrede": "WiFi Convidados", "Hosts Requeridos": 30},
            {"Subrede": "Lan RH", "Hosts Requeridos": 10},
            {"Subrede": "Link Gateway", "Hosts Requeridos": 2}
        ])
        
        edited_demands = st.data_editor(
            default_demands,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Subrede": st.column_config.TextColumn("Nome da Subrede", required=True),
                "Hosts Requeridos": st.column_config.NumberColumn("Hosts Requeridos", min_value=1, step=1, required=True)
            }
        )

    with col_v2:
        st.subheader("Plano de Alocação Calculado")
        
        if st.button("Calcular VLSM", type="primary", use_container_width=True):
            try:
                base_net = ipaddress.IPv4Network(vlsm_base_input.strip(), strict=False)
                
                # Filtrar e sanitizar demandas
                demands_list = []
                for idx, row in edited_demands.iterrows():
                    name = str(row.get("Subrede", f"Subrede {idx}")).strip()
                    hosts_req = row.get("Hosts Requeridos")
                    if name and pd.notna(hosts_req):
                        demands_list.append({"name": name, "hosts": int(hosts_req)})
                
                if not demands_list:
                    st.warning("Adicione pelo menos uma demanda de hosts.")
                else:
                    # Algoritmo VLSM: Ordenar demandas decrescentemente
                    sorted_demands = sorted(demands_list, key=lambda x: x["hosts"], reverse=True)
                    
                    allocated_list = []
                    current_address = base_net.network_address
                    overflow = False
                    
                    for d in sorted_demands:
                        req_hosts = d["hosts"]
                        name = d["name"]
                        
                        # Total necessário: hosts + rede + broadcast
                        needed_ips = req_hosts + 2
                        
                        # Achar tamanho do bloco (potência de 2)
                        if needed_ips <= 2:
                            block_size = 4  # Mínimo /30
                        else:
                            block_size = 2 ** math.ceil(math.log2(needed_ips))
                            
                        # Determinar prefixo
                        prefix = 32 - int(math.log2(block_size))
                        
                        # Alinhamento de limite (IP inicial deve ser múltiplo do tamanho do bloco)
                        current_int = int(current_address)
                        if current_int % block_size != 0:
                            current_int = ((current_int // block_size) + 1) * block_size
                            current_address = ipaddress.IPv4Address(current_int)
                        
                        # Criar objeto da subrede
                        subnet = ipaddress.IPv4Network(f"{current_address}/{prefix}", strict=True)
                        
                        # Verificar se ultrapassa a rede base
                        if not base_net.supernet_of(subnet):
                            st.error(
                                f"🚨 **Estouro de Espaço!** A subrede '{name}' ({req_hosts} hosts) "
                                f"requer bloco de tamanho {block_size} (prefixo /{prefix}), "
                                f"o que excede os limites da rede base {vlsm_base_input}."
                            )
                            overflow = True
                            break
                            
                        allocated_list.append({
                            "Subrede": name,
                            "Hosts Solicitados": req_hosts,
                            "Hosts Úteis (Alocados)": block_size - 2,
                            "Faixa de Rede CIDR": str(subnet),
                            "Primeiro Host": str(subnet.network_address + 1),
                            "Último Host": str(subnet.broadcast_address - 1),
                            "Broadcast": str(subnet.broadcast_address),
                            "Máscara Decimal": str(subnet.netmask)
                        })
                        
                        # Avança ponteiro de alocação para depois do broadcast
                        current_address = subnet.broadcast_address + 1
                    
                    if allocated_list and not overflow:
                        st.success(" VLSM calculado com sucesso!")
                        df_allocated = pd.DataFrame(allocated_list)
                        st.dataframe(df_allocated, use_container_width=True, hide_index=True)
                        
                        # Calcular estatísticas de ocupação
                        total_allocated_ips = sum(row["Hosts Úteis (Alocados)"] + 2 for row in allocated_list)
                        occupancy_percent = (total_allocated_ips / base_net.num_addresses) * 100
                        
                        st.divider()
                        st.markdown(f"**Estatísticas de Ocupação da Rede Base:**")
                        st.write(f"- IPs Totais da Rede Base: **{base_net.num_addresses}**")
                        st.write(f"- IPs Alocados no VLSM (incluindo rede/broadcast): **{total_allocated_ips}**")
                        st.progress(min(1.0, occupancy_percent / 100))
                        st.write(f"- Taxa de Uso da Rede Base: **{occupancy_percent:.2f}%**")
                        
                        # Baixar CSV
                        csv_vlsm = df_allocated.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Baixar Planejamento VLSM (CSV)",
                            csv_vlsm,
                            "planejamento_vlsm.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                        
            except ValueError as e:
                st.error(f"Erro na Rede Base: {e}. Certifique-se de usar notação CIDR válida (ex: 192.168.0.0/24).")

# ================= TAB 3: SUMARIZAÇÃO DE ROTAS =================
with tab_sum:
    st.header("Sumarização de Rotas (CIDR Aggregation)")
    st.markdown(
        "A sumarização de rotas agrupa várias redes CIDR consecutivas em um menor "
        "conjunto de rotas agregadas (supernets), diminuindo o tamanho das tabelas de roteamento."
    )
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        st.subheader("Subredes de Entrada")
        subnets_area = st.text_area(
            "Digite as subredes (uma por linha)",
            value="192.168.1.0/24\n192.168.2.0/24\n192.168.3.0/24\n10.0.0.0/24\n10.0.1.0/24",
            height=200,
            help="Informe subredes válidas com máscaras (ex: 192.168.0.0/24)."
        )
        
    with col_s2:
        st.subheader("Rotas Sumarizadas Calculadas")
        
        if st.button("Sumarizar Redes", type="primary", use_container_width=True):
            input_lines = [line.strip() for line in subnets_area.split("\n") if line.strip()]
            subnets_objects = []
            invalid_lines = []
            
            for line in input_lines:
                try:
                    net_obj = ipaddress.IPv4Network(line, strict=False)
                    subnets_objects.append(net_obj)
                except ValueError:
                    invalid_lines.append(line)
            
            if invalid_lines:
                st.warning(f"As seguintes linhas foram ignoradas por conterem IPs/CIDR inválidos: {invalid_lines}")
                
            if not subnets_objects:
                st.error("Nenhuma rede válida foi informada.")
            else:
                # Calcular sumarização
                try:
                    collapsed = list(ipaddress.collapse_addresses(subnets_objects))
                    st.success("Sumarização concluída!")
                    
                    df_sum = pd.DataFrame([
                        {
                            "Rota Sumarizada": str(net),
                            "Máscara Decimal": str(net.netmask),
                            "IP de Rede": str(net.network_address),
                            "IP de Broadcast": str(net.broadcast_address),
                            "Hosts Cobertos": f"{net.num_addresses - 2 if net.prefixlen <= 30 else net.num_addresses:,}"
                        }
                        for net in collapsed
                    ])
                    st.dataframe(df_sum, use_container_width=True, hide_index=True)
                    
                except Exception as e:
                    st.error(f"Erro ao colapsar endereços: {e}")

# ================= TAB 4: PLANEJAMENTO IPV6 =================
with tab_ipv6:
    st.header("Planejamento e Ferramentas IPv6")
    
    tab_v6_calc, tab_v6_sub = st.tabs([
        "🔍 Compressão & Tipo IPv6",
        "🔀 Divisão de Subredes IPv6"
    ])
    
    with tab_v6_calc:
        ipv6_input = st.text_input("Endereço IPv6", value="2001:0db8:0000:0000:0000:0000:0000:0001")
        
        if ipv6_input:
            try:
                ip6 = ipaddress.IPv6Address(ipv6_input.strip())
                
                c_v6_1, c_v6_2 = st.columns(2)
                with c_v6_1:
                    st.text_area("Formato Comprimido (Forma Curta)", value=ip6.compressed, disabled=True)
                with c_v6_2:
                    st.text_area("Formato Expandido (Forma Longa)", value=ip6.exploded, disabled=True)
                    
                # Classificação
                scope_label = get_ipv6_scope_label(ip6)
                
                st.divider()
                st.markdown(f"**Classificação de Escopo:**")
                st.info(f"O endereço inserido é do tipo: **{scope_label}**")
                
            except ValueError as e:
                st.error(f"Endereço IPv6 inválido: {e}")
                
    with tab_v6_sub:
        st.markdown(
            "Configure uma rede base IPv6 e o prefixo desejado para simular o fatiamento em subredes."
        )
        
        col_v6_s1, col_v6_s2 = st.columns(2)
        with col_v6_s1:
            base_v6_net = st.text_input("Rede Base IPv6", value="2001:db8:acad::/48")
        with col_v6_s2:
            target_v6_prefix = st.slider("Prefixo das Subredes", min_value=16, max_value=128, value=64)
            
        if st.button("Gerar Subredes IPv6", type="primary", use_container_width=True):
            try:
                net6 = ipaddress.IPv6Network(base_v6_net.strip(), strict=False)
                base_pref = net6.prefixlen
                
                if target_v6_prefix < base_pref:
                    st.error("O prefixo das subredes deve ser maior ou igual ao prefixo da rede base!")
                else:
                    diff = target_v6_prefix - base_pref
                    total_subnets = 2 ** diff
                    
                    st.success("Divisão calculada!")
                    st.write(f"Quantidade total de subredes `/{target_v6_prefix}` possíveis: **{total_subnets:,}**")
                    
                    # Gerador de subredes
                    subnets_gen = net6.subnets(new_prefix=target_v6_prefix)
                    
                    # Exibir apenas os primeiros como exemplo para não travar
                    sample_size = min(total_subnets, 15)
                    samples = []
                    
                    for i in range(sample_size):
                        sub = next(subnets_gen)
                        samples.append({
                            "Subrede": i + 1,
                            "Rede CIDR": str(sub),
                            "IP de Rede Inicial": str(sub.network_address),
                            "Broadcast/Final": str(sub.broadcast_address)
                        })
                        
                    df_v6 = pd.DataFrame(samples)
                    st.dataframe(df_v6, use_container_width=True, hide_index=True)
                    
                    if total_subnets > sample_size:
                        st.info(f"Mostrando as primeiras {sample_size} subredes de exemplo. A última subrede calculada é:")
                        # Obter a última subrede calculando o offset diretamente
                        last_network_int = int(net6.network_address) + (total_subnets - 1) * (2 ** (128 - target_v6_prefix))
                        last_subnet = ipaddress.IPv6Network(f"{ipaddress.IPv6Address(last_network_int)}/{target_v6_prefix}")
                        st.code(f"Última Subrede: {last_subnet}", language="text")
                        
            except ValueError as e:
                st.error(f"Rede base IPv6 inválida: {e}")
