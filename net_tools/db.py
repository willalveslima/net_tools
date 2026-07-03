import sqlite3
import json
from datetime import datetime
from typing import Optional

DB_NAME = "net_tools.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,

            target TEXT,
            origin_ip TEXT,
            destination_ip TEXT,

            avg_ping REAL,
            packet_loss REAL,

            open_ports INTEGER,
            total_hops INTEGER,

            raw_json TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_nodes (
            ip TEXT PRIMARY KEY,
            hostname TEXT,
            last_seen TEXT,
            type TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_edges (
            source_ip TEXT,
            target_ip TEXT,
            last_seen TEXT,
            PRIMARY KEY (source_ip, target_ip),
            FOREIGN KEY (source_ip) REFERENCES network_nodes(ip) ON DELETE CASCADE,
            FOREIGN KEY (target_ip) REFERENCES network_nodes(ip) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subnets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cidr TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subnet_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subnet_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY (subnet_id) REFERENCES subnets(id) ON DELETE CASCADE
        )
        """)
        conn.commit()


def save_test_result(result: dict):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    target = result.get("target")
    origin_ip = result.get("origin_ip")

    # destino
    if result.get("is_ip"):
        destination_ip = target
    else:
        dns = result.get("dns", {})
        addresses = dns.get("addresses") or []
        destination_ip = ",".join(addresses)

    # ping
    ping_summary = result.get("ping", {}).get("summary", {})
    avg_ping = ping_summary.get("avg_ms")
    packet_loss = ping_summary.get("packet_loss_percent")

    # hops
    total_hops = len(result.get("hops", []))

    # portas
    tcp = result.get("tcp", [])
    open_ports = len([p for p in tcp if p.get("open")])

    raw_json = json.dumps(result)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO test_results (
            timestamp,
            target,
            origin_ip,
            destination_ip,
            avg_ping,
            packet_loss,
            open_ports,
            total_hops,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            target,
            origin_ip,
            destination_ip,
            avg_ping,
            packet_loss,
            open_ports,
            total_hops,
            raw_json
        ))
        conn.commit()


def load_test_history():
    """
    Retorna o histórico completo de testes como um DataFrame do Pandas.
    """
    import pandas as pd
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM test_results ORDER BY id DESC",
            conn
        )
    return df


def save_node(ip: str, hostname: str, node_type: str, timestamp: str):
    """
    Salva ou atualiza um nó de rede na tabela network_nodes.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, type FROM network_nodes WHERE ip = ?", (ip,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO network_nodes (ip, hostname, last_seen, type) VALUES (?, ?, ?, ?)",
                (ip, hostname or "", timestamp, node_type)
            )
        else:
            old_hostname, old_type = row
            # Atualiza tipo se o novo tipo for mais prioritário (ex: 'origin' ou 'target' são prioritários)
            updated_type = old_type
            if node_type == "origin":
                updated_type = "origin"
            elif node_type == "target" and old_type != "origin":
                updated_type = "target"
            
            # Atualiza o hostname se vier um nome válido e o antigo estiver vazio
            updated_hostname = old_hostname
            if hostname and (not old_hostname or old_hostname == "*" or old_hostname == "N/D"):
                updated_hostname = hostname

            cursor.execute(
                "UPDATE network_nodes SET hostname = ?, last_seen = ?, type = ? WHERE ip = ?",
                (updated_hostname, timestamp, updated_type, ip)
            )
        conn.commit()


def save_edge(source_ip: str, target_ip: str, timestamp: str):
    """
    Salva ou atualiza uma conexão (aresta) entre dois nós na tabela network_edges.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM network_edges WHERE source_ip = ? AND target_ip = ?",
            (source_ip, target_ip)
        )
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO network_edges (source_ip, target_ip, last_seen) VALUES (?, ?, ?)",
                (source_ip, target_ip, timestamp)
            )
        else:
            cursor.execute(
                "UPDATE network_edges SET last_seen = ? WHERE source_ip = ? AND target_ip = ?",
                (timestamp, source_ip, target_ip)
            )
        conn.commit()


def save_traceroute_path(origin_ip: str, hops: list, target: str):
    """
    Mapeia e persiste os nós e arestas de um teste de traceroute concluído.
    """
    if not origin_ip:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Filtrar hops válidos que possuem IP
    valid_hops = []
    for h in hops:
        ip = h.get("ip")
        if ip and ip != "*" and ip != "N/D" and ip.strip():
            valid_hops.append(h)

    # 1. Salvar nó de origem
    save_node(origin_ip, "Origem (Local)", "origin", timestamp)

    path_ips = [origin_ip]

    # 2. Salvar nós identificados no traceroute
    for i, hop in enumerate(valid_hops):
        ip = hop.get("ip")
        hostname = hop.get("hostname")
        if hostname == "*" or hostname == "N/D":
            hostname = ""

        # O último hop válido é marcado como 'target', senão 'intermediate'
        is_last = (i == len(valid_hops) - 1)
        node_type = "target" if is_last else "intermediate"

        save_node(ip, hostname, node_type, timestamp)
        path_ips.append(ip)

    # 3. Salvar conexões (arestas) consecutivas
    for i in range(len(path_ips) - 1):
        src = path_ips[i]
        dst = path_ips[i + 1]
        if src != dst:  # Evita loops para si mesmo
            save_edge(src, dst, timestamp)


def get_network_graph() -> dict:
    """
    Retorna todos os nós e arestas mapeados no banco.
    """
    nodes = []
    edges = []

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Nós
        cursor.execute("SELECT ip, hostname, last_seen, type FROM network_nodes")
        for row in cursor.fetchall():
            nodes.append({
                "ip": row["ip"],
                "hostname": row["hostname"],
                "last_seen": row["last_seen"],
                "type": row["type"]
            })

        # Arestas
        cursor.execute("SELECT source_ip, target_ip, last_seen FROM network_edges")
        for row in cursor.fetchall():
            edges.append({
                "source": row["source_ip"],
                "target": row["target_ip"],
                "last_seen": row["last_seen"]
            })

    return {"nodes": nodes, "edges": edges}


def clear_network_map():
    """
    Limpa permanentemente todos os registros de nós e conexões do mapa de rede.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM network_nodes")
        cursor.execute("DELETE FROM network_edges")
        conn.commit()


def save_subnet(name: str, cidr: str):
    """
    Cadastra uma subrede no banco de dados.
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO subnets (name, cidr, created_at) VALUES (?, ?, ?)",
            (name.strip(), cidr.strip(), timestamp)
        )
        conn.commit()


def delete_subnet(subnet_id: int):
    """
    Exclui uma subrede e todos os seus scans associados (cascade).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subnet_scans WHERE subnet_id = ?", (subnet_id,))
        cursor.execute("DELETE FROM subnets WHERE id = ?", (subnet_id,))
        conn.commit()


def list_subnets() -> list:
    """
    Lista todas as subredes cadastradas.
    """
    subnets = []
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, cidr, created_at FROM subnets ORDER BY name ASC")
        for row in cursor.fetchall():
            subnets.append({
                "id": row["id"],
                "name": row["name"],
                "cidr": row["cidr"],
                "created_at": row["created_at"]
            })
    return subnets


def save_subnet_scan(subnet_id: int, active_hosts: list):
    """
    Grava os hosts ativos descobertos no teste atual de scan no banco.
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_json = json.dumps(active_hosts)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO subnet_scans (subnet_id, timestamp, raw_json) VALUES (?, ?, ?)",
            (subnet_id, timestamp, raw_json)
        )
        conn.commit()


def get_last_subnet_scan(subnet_id: int) -> Optional[dict]:
    """
    Retorna o scan mais recente executado para uma subrede, se houver.
    """

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, raw_json FROM subnet_scans WHERE subnet_id = ? ORDER BY id DESC LIMIT 1",
            (subnet_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "active_hosts": json.loads(row["raw_json"])
            }
    return None