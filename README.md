# Net Tools

Ferramenta web em Python para suporte de rede, com interface em Streamlit.

## Recursos

- Resolução DNS do destino com medição de tempo;
- Ping no destino;
- Tracert/traceroute com resolução reversa de nomes dos hops;
- MTR-like por hop intermediário, preservando hostname do traceroute;
- Checagem de portas TCP com execução paralela;
- Controles na interface para habilitar/desabilitar testes;
- Exportação CSV para MTR-like e TCP;
- Exportação JSON completa.

## Estrutura

```text
net_tools_v3_hostname/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml
└── net_tools/
    ├── __init__.py
    ├── checks.py
    └── utils.py
```

## Instalação no Windows

```powershell
python -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
```

## Execução

Use preferencialmente:

```powershell
python -m streamlit run app.py
```

## Uso

1. Informe um domínio ou IP.
2. Ajuste os controles na barra lateral.
3. Para portas TCP, use lista e/ou intervalos:

```text
22,53,80,443,445,1433,1521,3389,8000-8010
```

4. Clique em **Executar testes**.
5. Consulte os resultados nas abas.

## Observações técnicas

- Se a entrada for IP, o DNS do destino é ignorado automaticamente.
- O traceroute é executado em modo numérico (`tracert -d` no Windows / `traceroute -n` em Linux) para evitar lentidão nativa.
- A resolução de nomes dos hops é feita depois, em paralelo, por consulta reversa/PTR.
- Nem todo hop possui PTR publicado; nesses casos o campo `hostname` fica vazio.
- A checagem TCP valida abertura de conexão TCP, semelhante a um teste básico de telnet/netcat.
- Perda ICMP em hop intermediário não significa obrigatoriamente falha, pois muitos roteadores limitam ou bloqueiam ICMP.
