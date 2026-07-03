import pandas as pd
import streamlit as st
import datetime

from net_tools.state import init_state
from net_tools.checks import service_curl_batch_test

# Inicializa o estado global da aplicação
init_state()

st.set_page_config(
    page_title="Diagnóstico de Serviços HTTP",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⏱️ Diagnóstico de Serviços (Métricas HTTP)")
st.markdown(
    "Essa página analisa a disponibilidade e as latências detalhadas de rede (DNS, Conexão TCP, "
    "Handshake TLS, TTFB e Tempo Total) de múltiplos endpoints de voz ou serviços web usando o comando `curl` local."
)

# Configurações do Teste na Barra Lateral
st.sidebar.header("⚙️ Opções do Teste")

timeout_s = st.sidebar.slider(
    "Timeout por Requisição (s)",
    min_value=1,
    max_value=30,
    value=10,
    help="Tempo limite máximo para cada consulta de serviço."
)

insecure = st.sidebar.checkbox(
    "Ignorar validação SSL/TLS (-k)",
    value=True,
    help="Útil para testar endpoints internos ou servidores com certificados autoassinados ou expirados."
)

max_workers = st.sidebar.slider(
    "Paralelismo (Max Workers)",
    min_value=1,
    max_value=20,
    value=5,
    help="Número de consultas simultâneas em segundo plano."
)

# Entrada de URLs
st.subheader("Endpoints para Diagnóstico")
default_urls = (
    "https://rioacwrtc01.cxonevoice.com\n"
    "https://spracwrtc02.cxonevoice.com\n"
    "https://www.google.com\n"
    "https://www.cloudflare.com"
)

urls_input = st.text_area(
    "Insira as URLs dos serviços (uma por linha)",
    value=default_urls,
    height=150,
    placeholder="Ex:\nhttps://servico1.local\nhttps://servico2.com"
)

# Inicializa sessão para manter o resultado persistido em re-runs
if "last_services_result" not in st.session_state:
    st.session_state.last_services_result = None

# Função de estilização condicional para a tabela de latência
def color_latency_and_status(val, col_type):
    if val is None or pd.isna(val):
        return "color: gray"
    
    if col_type == "status":
        # Status de sucesso HTTP (200, 3xx, 400 - se respondeu, está ativo)
        if val == "Falha" or val == 0:
            return "background-color: #7f1d1d; color: #fecaca; font-weight: bold;"
        return "background-color: #14532d; color: #dcfce7;"
        
    elif col_type == "latency":
        if val >= 1000:  # Muito lento (> 1s)
            return "color: #ef4444; font-weight: bold;"
        elif val >= 300:  # Médio
            return "color: #f59e0b;"
        else:  # Rápido
            return "color: #10b981;"
            
    return ""

if st.button("🚀 Iniciar Diagnóstico de Serviços", type="primary", use_container_width=True):
    # Parse das URLs
    urls = [line.strip() for line in urls_input.split("\n") if line.strip()]
    
    if not urls:
        st.warning("Insira pelo menos uma URL válida para testar!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total, msg):
            progress_bar.progress(current / total)
            status_text.text(f"⏳ {msg} ({current}/{total})")
            
        try:
            # Executar lote de pings curl
            results = service_curl_batch_test(
                urls=urls,
                timeout_s=timeout_s,
                insecure=insecure,
                max_workers=max_workers,
                progress_callback=update_progress
            )
            
            progress_bar.progress(1.0)
            status_text.success("Diagnóstico concluído! ✅")
            
            # Salva resultado no state
            st.session_state.last_services_result = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "results": results
            }
            
        except Exception as e:
            st.error(f"Erro na varredura dos serviços: {e}")

# Exibição de Resultados
res = st.session_state.last_services_result

if res:
    st.divider()
    st.subheader("Métricas de Latência de Serviços")
    st.caption(f"Executado em: {res['timestamp']}")
    
    results = res["results"]
    
    # Calcular estatísticas rápidas
    total_services = len(results)
    successful_services = sum(1 for r in results if r["success"])
    active_percent = (successful_services / total_services) * 100 if total_services > 0 else 0
    
    avg_total_time = 0
    valid_times = [r["total_ms"] for r in results if r["success"] and r["total_ms"] is not None]
    if valid_times:
        avg_total_time = sum(valid_times) / len(valid_times)
        
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total de Endpoints", total_services)
    with c2:
        st.metric("Endpoints Ativos / Respondendo", f"{successful_services} ({active_percent:.1f}%)")
    with c3:
        st.metric("Tempo Médio de Resposta (Ativos)", f"{avg_total_time:.2f} ms")
        
    # Converter para DataFrame
    rows = []
    for r in results:
        rows.append({
            "Serviço (URL)": r["url"],
            "Código HTTP": r["http_code"] if r["success"] else "Falha",
            "DNS (ms)": r["dns_ms"],
            "Conexão TCP (ms)": r["connect_ms"],
            "TLS Handshake (ms)": r["tls_ms"],
            "TTFB (ms)": r["ttfb_ms"],
            "Tempo Total (ms)": r["total_ms"],
            "Erro / Detalhe": r["error"] or "Operação bem sucedida"
        })
        
    df = pd.DataFrame(rows)
    
    # Estilização condicional de colunas
    styled_df = df.style\
        .map(lambda v: color_latency_and_status(v, "status"), subset=["Código HTTP"])\
        .map(lambda v: color_latency_and_status(v, "latency"), subset=["DNS (ms)", "Conexão TCP (ms)", "TLS Handshake (ms)", "TTFB (ms)", "Tempo Total (ms)"])
        
    st.markdown("### Tabela Consolidada")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Exportar CSV
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Baixar Relatório de Diagnóstico (CSV)",
        csv_data,
        f"diagnostico_servicos_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # Gráfico Comparativo
    st.markdown("### Comparação Gráfica de Tempo de Resposta (Total)")
    df_chart = df[df["Código HTTP"] != "Falha"].copy()
    if not df_chart.empty:
        df_chart_view = df_chart[["Serviço (URL)", "Tempo Total (ms)"]]
        st.bar_chart(df_chart_view, x="Serviço (URL)", y="Tempo Total (ms)", color="#10B981")
    else:
        st.info("Nenhum serviço disponível para plotar no gráfico de tempo de resposta.")
        
    # Saída detalhada (Console do curl)
    st.markdown("### Detalhes da Execução Bruta (Console curl)")
    for idx, r in enumerate(results):
        with st.expander(f"curl stdout/stderr: {r['url']}"):
            st.code(f"Comando executado:\n> curl -w ... -s -m {timeout_s} {'-k ' if insecure else ''}{r['url']}\n\nSaída do console:\n{r['stdout'] or r['error']}", language="text")
