import streamlit as st
from net_tools.utils import resolve_dns

from net_tools.state import init_state
init_state()


st.title("🌐 DNS")

host = st.text_input("Domínio")

if st.button("Resolver"):
    st.json(resolve_dns(host))