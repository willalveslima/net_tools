import json
import datetime
import streamlit as st
import streamlit.components.v1 as components

from net_tools.state import init_state
from net_tools.db import get_network_graph, clear_network_map

# Inicializa o estado da aplicação
init_state()

st.set_page_config(
    page_title="Mapa de Rede Interativo",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🗺️ Mapa de Rede Interativo")
st.markdown(
    "Este mapa visualiza a topologia acumulada de nós e conexões de rede identificados a partir dos testes de **Traceroute** executados no sistema."
)

# Sidebar - Configurações e Controles
st.sidebar.header("⚙️ Painel de Controle")

# 1. Filtro de Tempo
filter_age = st.sidebar.selectbox(
    "Filtrar detecções por período",
    ["Todos os registros", "Últimas 24 horas", "Últimos 7 dias"],
    index=0
)

# 2. Física do Grafo
physics_enabled = st.sidebar.checkbox(
    "Ativar simulação física elástica",
    value=True,
    help="Faz com que os nós se organizem dinamicamente usando forças de mola física. Desative se desejar travar a posição dos nós após estabilizarem."
)

st.sidebar.divider()

# 3. Limpar o Mapa
st.sidebar.subheader("⚠️ Zona de Perigo")
confirm_clear = st.sidebar.checkbox("Confirmar exclusão de dados")
if st.sidebar.button("Limpar Mapa de Rede", type="secondary", disabled=not confirm_clear, use_container_width=True):
    clear_network_map()
    st.sidebar.success("Topologia apagada com sucesso!")
    st.rerun()

# Carregar dados do banco de dados
graph_data = get_network_graph()
nodes = graph_data.get("nodes", [])
edges = graph_data.get("edges", [])

# Filtragem de dados por tempo de atividade
filtered_nodes = []
filtered_edges = []

if filter_age == "Todos os registros":
    filtered_nodes = nodes
    filtered_edges = edges
else:
    now = datetime.datetime.now()
    if filter_age == "Últimas 24 horas":
        limit = now - datetime.timedelta(days=1)
    else:  # Últimos 7 dias
        limit = now - datetime.timedelta(days=7)

    valid_node_ips = set()
    
    # Filtrar nós
    for node in nodes:
        try:
            seen_time = datetime.datetime.strptime(node["last_seen"], "%Y-%m-%d %H:%M:%S")
            if seen_time >= limit:
                filtered_nodes.append(node)
                valid_node_ips.add(node["ip"])
        except Exception:
            # Fallback caso a data esteja em formato diferente ou corrompida
            filtered_nodes.append(node)
            valid_node_ips.add(node["ip"])

    # Filtrar conexões (edges) - mantendo apenas se ambos os nós de origem e destino existem
    for edge in edges:
        try:
            seen_time = datetime.datetime.strptime(edge["last_seen"], "%Y-%m-%d %H:%M:%S")
            if seen_time >= limit and edge["source"] in valid_node_ips and edge["target"] in valid_node_ips:
                filtered_edges.append(edge)
        except Exception:
            if edge["source"] in valid_node_ips and edge["target"] in valid_node_ips:
                filtered_edges.append(edge)

# Verificação se o mapa está vazio
if not filtered_nodes:
    st.info(
        """
        ### ℹ️ Mapa de Rede Vazio
        Nenhum nó de rede foi mapeado ainda (ou os filtros removeram todos os registros). 
        
        **Como popular o mapa:**
        1. Vá para a página [🔎 Teste Completo](Teste_Completo) ou [📡 Diagnóstico de Rede](Diagnostico_Rede).
        2. Execute um teste informando um Host de destino (ex.: `www.google.com` ou `8.8.8.8`).
        3. O teste executará o **Traceroute** descobrindo os saltos do caminho.
        4. O sistema gravará de forma automática esses nós e conexões no banco de dados.
        5. Volte aqui para ver seu mapa de rede desenhado interativamente!
        """
    )
else:
    # Exibir métricas da rede mapeada
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Nós Mapeados", len(filtered_nodes))
    with col2:
        st.metric("Total de Conexões Ativas", len(filtered_edges))

    # Formatar dados para o vis.js
    vis_nodes = []
    for node in filtered_nodes:
        ip = node["ip"]
        hostname = node["hostname"]
        node_type = node["type"]
        last_seen = node["last_seen"]

        # Label do nó
        label = f"{hostname}\n({ip})" if hostname and hostname != ip else ip
        
        # Tooltip HTML
        title = f"""
        <div style="line-height: 1.4;">
            <b>Endereço IP:</b> {ip}<br>
            <b>Nome Host:</b> {hostname or 'N/D'}<br>
            <b>Tipo de Nó:</b> {node_type.upper()}<br>
            <b>Última Detecção:</b> {last_seen}
        </div>
        """

        # Estilo de cor e tamanho do nó baseado no tipo
        if node_type == "origin":
            background = "#06B6D4"  # Cyan neon
            border = "#E0F2FE"
            size = 25
            label_color = "#38BDF8"
        elif node_type == "target":
            background = "#EF4444"  # Vermelho neon
            border = "#FEE2E2"
            size = 20
            label_color = "#F87171"
        else:  # intermediate
            background = "#F59E0B"  # Laranja/Amber
            border = "#FEF3C7"
            size = 14
            label_color = "#FBBF24"

        vis_nodes.append({
            "id": ip,
            "label": label,
            "title": title,
            "size": size,
            "color": {
                "background": background,
                "border": border,
                "highlight": {
                    "background": background,
                    "border": "#ffffff"
                },
                "hover": {
                    "background": background,
                    "border": "#ffffff"
                }
            },
            "font": {
                "color": label_color,
                "size": 11,
                "strokeWidth": 2,
                "strokeColor": "#0F172A"
            }
        })

    vis_edges = []
    for edge in filtered_edges:
        vis_edges.append({
            "from": edge["source"],
            "to": edge["target"],
            "title": f"Conexão detectada em: {edge['last_seen']}",
            "color": {
                "color": "#475569",
                "highlight": "#10B981",
                "hover": "#10B981"
            }
        })

    # Renderização do template HTML com vis.js
    html_template = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #0F172A; /* Slate 900 */
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            #network-container {{
                width: 100%;
                height: 100%;
            }}
            /* Estilo elegante para tooltips */
            div.vis-network div.vis-tooltip {{
                position: absolute;
                visibility: hidden;
                padding: 10px;
                white-space: nowrap;
                font-family: inherit;
                font-size: 13px;
                background-color: #1E293B; /* Slate 800 */
                color: #F8FAFC; /* Slate 50 */
                border: 1px solid #475569; /* Slate 600 */
                border-radius: 8px;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15);
                z-index: 1000;
            }}
        </style>
    </head>
    <body>
        <div id="network-container"></div>
        <script type="text/javascript">
            var nodes = new vis.DataSet({json.dumps(vis_nodes)});
            var edges = new vis.DataSet({json.dumps(vis_edges)});

            var container = document.getElementById('network-container');
            var data = {{
                nodes: nodes,
                edges: edges
            }};

            var options = {{
                nodes: {{
                    shape: 'dot',
                    borderWidth: 2,
                    shadow: {{
                        enabled: true,
                        color: 'rgba(0,0,0,0.4)',
                        size: 4,
                        x: 2,
                        y: 2
                    }}
                }},
                edges: {{
                    width: 2,
                    arrows: {{
                        to: {{
                            enabled: true,
                            scaleFactor: 0.8
                        }}
                    }},
                    smooth: {{
                        type: 'cubicBezier',
                        forceDirection: 'none',
                        roundness: 0.4
                    }},
                    shadow: {{
                        enabled: true,
                        color: 'rgba(0,0,0,0.2)',
                        size: 3,
                        x: 1,
                        y: 1
                    }}
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 150,
                    navigationButtons: true,
                    keyboard: true
                }},
                physics: {{
                    enabled: {str(physics_enabled).lower()},
                    barnesHut: {{
                        gravitationalConstant: -12000,
                        centralGravity: 0.25,
                        springLength: 130,
                        springConstant: 0.035,
                        damping: 0.1,
                        avoidOverlap: 0.3
                    }},
                    stabilization: {{
                        enabled: true,
                        iterations: 150,
                        updateInterval: 25
                    }}
                }}
            }};

            var network = new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """

    # Iframe de visualização em tela cheia com altura ajustada
    components.html(html_template, height=650, scrolling=False)
