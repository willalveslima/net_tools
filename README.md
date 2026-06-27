# Net Tools 🌐

Ferramenta web em Python para diagnóstico, troubleshooting e gerenciamento de rede rodando localmente no Windows. Interface amigável, reativa e de alta performance construída em **Streamlit**.

---

## 🚀 Recursos Principais

* **Teste Completo**: Execução sequencial automatizada contendo análise DNS, Ping, Traceroute, MTR-like por hop intermediário e varredura de portas TCP, salvando todos os resultados de uma vez no banco de dados.
* **Diagnóstico Isolado**: Execução ágil de Ping e Traceroute individuais com gráficos de resposta e persistência de dados em tela (evita reset ao interagir com outros componentes).
* **Consulta DNS Avançada**: Resolução DNS rica suportando múltiplos registros comuns (`A`, `AAAA`, `MX`, `TXT`, `CNAME`, `NS`, `SOA`) com organização por abas e tabela geral.
* **MTR-like (My Traceroute)**: Identificação em tempo real de saltos (hops) com disparo paralelo de pings, coloração condicional de latências (`<20ms`, `20ms-80ms`, `>=80ms`) e alertas para perdas de pacotes superiores a 0%.
* **Checagem de Portas TCP**: Varredura assíncrona paralela (usando threads) de portas comuns ou faixas customizadas (ex: `80,443,8000-8010`) mapeando o estado da porta (aberta/fechada) e o serviço correspondente.
* **Histórico com Persistência SQLite**: Armazenamento completo no banco local `net_tools.db`. Possui filtros inteligentes (por IP de origem e Host de destino) e expansão do payload bruto de dados em formato JSON.
* **Downloads**: Suporte a exportação de dados para **CSV** (tabelas DNS, Traceroute, MTR, TCP e Histórico) e **TXT** (logs brutos do Ping).

---

## 📂 Estrutura do Repositório

```text
net_tools/
├── app.py                     # Menu principal da aplicação Streamlit
├── requirements.txt           # Dependências do projeto (streamlit, pandas, dnspython)
├── README.md                  # Documentação do projeto
├── net_tools.db               # Banco de dados SQLite local (gerado na 1ª execução)
├── .streamlit/
│   └── config.toml            # Parametrizações de interface e tema do Streamlit
├── net_tools/                 # Módulos Python em segundo plano
│   ├── __init__.py
│   ├── checks.py              # Lógica das funções de teste de rede
│   ├── db.py                  # Abstração de conexões e queries do SQLite (with statement)
│   ├── state.py               # Injeção e controle do estado de configurações globais
│   └── utils.py               # Parsers e utilitários de subprocessos do Windows (cp850)
└── pages/                     # Telas individuais do dashboard Streamlit
    ├── 1_🔎_Teste_Completo.py
    ├── 2_📡_Diagnostico_Rede.py
    ├── 3_🔐_Portas_TCP.py
    ├── 4_🌐_DNS.py
    ├── 5_⚙️_Configuracoes.py
    ├── 6_📊_MTR.py
    └── 7_📜_Historico.py
```

---

## ⚙️ Instalação no Windows

1. Certifique-se de ter o Python 3.10+ instalado no seu sistema Windows.
2. No diretório do projeto, crie e ative o ambiente virtual virtualenv:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Instale os pacotes requeridos:
   ```powershell
   pip install -r requirements.txt
   ```

---

## 🖥️ Execução

Para iniciar o servidor web Streamlit na sua máquina local, execute:
```powershell
streamlit run app.py
```
Por padrão, a interface será aberta no seu navegador em: **http://localhost:8501**

---

## 💡 Observações Técnicas Importantes

* **Compatibilidade Windows**: A ferramenta consome comandos de rede do Windows nativos via subprocesso (`ping`, `tracert`, `ipconfig`). A codificação é tratada como `cp850` para evitar travamentos de caracteres no terminal brasileiro.
* **Resolução Reversa**: Hops intermediários do Traceroute são resolvidos em paralelo de forma assíncrona. Caso um roteador do meio do caminho não possua PTR publicado ou bloqueie ICMP, o campo hostname aparecerá em branco ou o hop indicará timeout, o que é esperado no comportamento de redes reais.
* **Desempenho**: Varreduras TCP e pings MTR usam `ThreadPoolExecutor` parametrizado por `max_workers` para evitar travamentos e entregar respostas rápidas.
