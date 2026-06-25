import streamlit as st
from net_tools.state import init_state
from net_tools.db import init_db

# inicializa banco
init_db()

st.set_page_config(page_title="Net Tools", page_icon="🌐")

# 🔥 ESSENCIAL
init_state()

st.title("🌐 Net Tools")
st.subheader("Plataforma de diagnóstico de rede")

st.markdown("### Escolha o modo")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔎 Teste Completo"):
        st.switch_page("pages/1_🔎_Teste_Completo.py")

with col2:
    if st.button("🧩 Testes Separados"):
        st.switch_page("pages/2_📡_Diagnostico_Rede.py")

st.write("Configuração atual:")
st.json(st.session_state.config)