import sqlite3
import json
from datetime import datetime


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