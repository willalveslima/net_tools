# Net Tools 🌐

Ferramenta web em Python para diagnóstico, troubleshooting e gerenciamento de rede rodando localmente no Windows. Interface amigável, reativa e de alta performance construída em **Streamlit**.

---

## 🚀 Recursos Principais

* **Teste Completo**: Execução sequencial automatizada contendo análise DNS, Ping, Traceroute, MTR-like por hop intermediário e varredura de portas TCP, salvando todos os resultados de uma vez no banco de dados.
* **Diagnóstico Isolado**: Execução ágil de Ping e Traceroute individuais com gráficos de resposta e persistência de dados em tela (evita reset ao interagir com outros componentes).
* **Consulta DNS Avançada**: Resolução DNS rica suportando múltiplos registros comuns (`A`, `AAAA`, `MX`, `TXT`, `CNAME`, `NS`, `SOA`) com organização por abas e tabela geral.
* **MTR-like (My Traceroute)**: Identificação em tempo real de saltos (hops) com disparo paralelo de pings, coloração condicional de latências (`<20ms`, `20ms-80ms`, `>=80ms`) e alertas para perdas de pacotes superiores a 0%.
* **Checagem de Portas TCP**: Varredura assíncrona paralela (usando threads) de portas comuns ou faixas customizadas (ex: `80,443,8000-8010`) mapeando o estado da porta (aberta/fechada) e o serviço correspondente.
* **Mapa de Rede Interativo**: Mapeamento dinâmico e em tempo real da topologia acumulada dos caminhos e nós de rede detectados durante execuções de traceroute. Renderizado de forma elegante e interativa (zoom, arrastar nós, tooltips) usando a biblioteca Vis.js.
* **Varredura de Subrede**: Funcionalidade para cadastrar faixas CIDR locais (de `/24` a `/32`), disparar pings rápidos em paralelo para mapear hosts respondendo por ICMP na rede, arquivar o histórico de testes no SQLite e executar comparações automáticas de hosts que ficaram offline (perdidos) ou novos hosts ativos em relação ao último scan.
* **Calculadora Avançada de Redes**: Módulo utilitário interativo contendo quatro abas essenciais para analistas de rede:
  1. **Calculadora IPv4**: Detalhamento completo de IP/máscara, primeiro/último host utilizável, wildcard, classe, escopo de endereço e representação binária perfeitamente alinhada.
  2. **Divisão VLSM**: Dimensionador automático de blocos de subredes com base em demandas de hosts de múltiplos segmentos (ordena por tamanho de host decrescente para alocação ótima de IPs), gera relatórios de ocupação de rede e exportação de CSV.
  3. **Sumarização de Rotas (CIDR Aggregation)**: Consolida conjuntos de rotas IPv4 consecutivas em supernets mínimas.
  4. **Planejamento IPv6**: Analisador de compressão/expansão de notações IPv6, classificação de tipo de escopo e fatiador de blocos IPv6 em subredes de exemplo (como `/48` para `/64`).
* **Histórico com Persistência SQLite**: Armazenamento completo no banco local `net_tools.db`. Possui filtros inteligentes (por IP de origem e Host de destino) e expansão do payload bruto de dados em formato JSON.
* **Downloads**: Suporte a exportação de dados para **CSV** (tabelas DNS, Traceroute, MTR, TCP, Histórico, Topologia, Subredes e Planos VLSM) e **TXT** (logs brutos do Ping).

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
│   ├── db.py                  # Abstração de conexões SQLite (persistência histórica e topológica)
│   ├── state.py               # Injeção e controle do estado de configurações globais
│   └── utils.py               # Parsers e utilitários de subprocessos do Windows (cp850)
└── pages/                     # Telas individuais do dashboard Streamlit
    ├── 1_🔎_Teste_Completo.py
    ├── 2_📡_Diagnostico_Rede.py
    ├── 3_🔐_Portas_TCP.py
    ├── 4_🌐_DNS.py
    ├── 5_⚙️_Configuracoes.py
    ├── 6_📊_MTR.py
    ├── 7_📜_Historico.py
    ├── 8_🗺️_Mapa_Rede.py      # Página dedicada para o mapa topológico interativo
    ├── 9_🌐_Scan_Subrede.py   # Página de varredura ICMP e comparação de deltas de subrede
    └── 10_🧮_Calculadora_Redes.py # Página dedicada à calculadora e planejamento de blocos IP
```

---

## ⚙️ Instalação no Windows

1. Certifique-se de ter o Python 3.10+ instalado no seu sistema Windows.
2. No diretório do projeto, crie e ative o ambiente virtual:
   ```powershell
   python -m venv .venv
   ```
3. Instale os pacotes requeridos:
   ```powershell
   .\.venv\Scripts\pip install -r requirements.txt
   ```

---

## 🖥️ Execução

Para iniciar o servidor web Streamlit na sua máquina local, execute:
```powershell
.\.venv\Scripts\streamlit run app.py
```
Por padrão, a interface será aberta no seu navegador em: **http://localhost:8501**

---

## 💡 Observações Técnicas Importantes

* **Compatibilidade Windows**: A ferramenta consome comandos de rede do Windows nativos via subprocesso (`ping`, `tracert`, `ipconfig`). A codificação é tratada como `cp850` para evitar travamentos de caracteres no terminal brasileiro.
* **Varredura de Subredes**: Limitada a faixas CIDR com máscaras entre `/24` e `/32` (máximo de 256 hosts) para evitar lentidão e esgotamento do limite de processos simultâneos do Windows.
* **Calculadora Local**: Toda a lógica de análise de IP, colapso CIDR, fatiamento IPv6 e VLSM é processada dinamicamente em memória usando a biblioteca padrão `ipaddress` do Python.
* **Desempenho**: Varreduras TCP, pings MTR e sweep de subrede usam `ThreadPoolExecutor` parametrizado por `max_workers` para evitar travamentos e entregar respostas rápidas.

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](file:///c:/Users/walve/Documents/Desenv/net_tools/LICENSE) - consulte o arquivo para detalhes.

