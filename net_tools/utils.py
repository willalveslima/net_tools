import ipaddress
import re
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional


COMMON_PORT_SERVICES = {
    20: "FTP-DATA",
    21: "FTP",
    22: "SSH",
    23: "TELNET",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    123: "NTP",
    135: "MS-RPC",
    139: "NETBIOS",
    143: "IMAP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    587: "SMTP-SUBMISSION",
    636: "LDAPS",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "ORACLE",
    3306: "MYSQL",
    3389: "RDP",
    5432: "POSTGRESQL",
    5900: "VNC",
    8080: "HTTP-ALT",
    8443: "HTTPS-ALT",
}


def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address((value or "").strip())
        return True
    except ValueError:
        return False


def normalize_target(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    value = value.split("/")[0]

    if value.count(":") == 1:
        host_part, port_part = value.rsplit(":", 1)
        if port_part.isdigit():
            value = host_part

    return value.strip().strip("[]")


def parse_ports(value: str) -> List[int]:
    """
    Aceita portas separadas por vírgula e intervalos.

    Exemplo:
    22,80,443,8000-8010
    """
    ports = set()

    for part in (value or "").split(","):
        part = part.strip()

        if not part:
            continue

        if "-" in part:
            start, end = part.split("-", 1)

            if start.strip().isdigit() and end.strip().isdigit():
                a, b = int(start), int(end)

                if 1 <= a <= b <= 65535:
                    ports.update(range(a, b + 1))

        elif part.isdigit():
            port = int(part)

            if 1 <= port <= 65535:
                ports.add(port)

    return sorted(ports)


def run_command(command: List[str], timeout: int = 20) -> Dict[str, object]:
    start = time.perf_counter()

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="cp850" if sys.platform.startswith("win") else "utf-8",
            errors="replace",
        )

        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "timeout": False,
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"Timeout após {timeout}s",
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "timeout": True,
        }

    except Exception as exc:
        return {
            "command": " ".join(command),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "timeout": False,
        }


def resolve_dns(host: str) -> Dict[str, object]:
    start = time.perf_counter()

    try:
        infos = socket.getaddrinfo(host, None)
        addresses = sorted({item[4][0] for item in infos})

        return {
            "success": True,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "addresses": addresses,
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "addresses": [],
            "error": str(exc),
        }


def reverse_dns(ip: str, timeout: float = 2.0) -> Optional[str]:
    old_timeout = socket.getdefaulttimeout()

    try:
        socket.setdefaulttimeout(timeout)
        return socket.gethostbyaddr(ip)[0]

    except Exception:
        return None

    finally:
        socket.setdefaulttimeout(old_timeout)


def ping_command(host: str, count: int = 4, timeout_ms: int = 1000) -> List[str]:
    if sys.platform.startswith("win"):
        return ["ping", "-n", str(count), "-w", str(timeout_ms), host]

    timeout_s = max(1, int(timeout_ms / 1000))
    return ["ping", "-c", str(count), "-W", str(timeout_s), host]


def traceroute_command(host: str, max_hops: int = 30) -> List[str]:
    if sys.platform.startswith("win"):
        return ["tracert", "-d", "-h", str(max_hops), host]

    return ["traceroute", "-n", "-m", str(max_hops), host]


def parse_ping_summary(output: str) -> Dict[str, Optional[float]]:
    """
    Extrai estatísticas do ping em Windows PT-BR, Windows EN e Linux.

    Retorna:
    - packet_loss_percent
    - min_ms
    - avg_ms
    - max_ms
    """
    packet_loss = None
    min_ms = None
    avg_ms = None
    max_ms = None

    # Windows PT-BR / EN:
    # (0% de perda) ou (0% loss)
    loss_match = re.search(
        r"\((\d+(?:[.,]\d+)?)%\s*(?:de\s*)?(?:perda|loss)\)",
        output,
        re.IGNORECASE,
    )

    if loss_match:
        packet_loss = float(loss_match.group(1).replace(",", "."))
    else:
        # Linux:
        # 0% packet loss
        linux_loss = re.search(
            r"(\d+(?:[.,]\d+)?)%\s*packet loss",
            output,
            re.IGNORECASE,
        )

        if linux_loss:
            packet_loss = float(linux_loss.group(1).replace(",", "."))

    # Windows PT-BR:
    # Mínimo = 1ms, Máximo = 2ms, Média = 1ms
    win_pt = re.search(
        r"M[íi]nimo\s*=\s*(\d+)ms.*?"
        r"M[áa]ximo\s*=\s*(\d+)ms.*?"
        r"M[ée]dia\s*=\s*(\d+)ms",
        output,
        re.IGNORECASE | re.DOTALL,
    )

    if win_pt:
        min_ms, max_ms, avg_ms = map(float, win_pt.groups())

    # Windows EN:
    # Minimum = 1ms, Maximum = 2ms, Average = 1ms
    win_en = re.search(
        r"Minimum\s*=\s*(\d+)ms.*?"
        r"Maximum\s*=\s*(\d+)ms.*?"
        r"Average\s*=\s*(\d+)ms",
        output,
        re.IGNORECASE | re.DOTALL,
    )

    if win_en:
        min_ms, max_ms, avg_ms = map(float, win_en.groups())

    # Linux:
    # rtt min/avg/max/mdev = 1.1/2.2/3.3/0.1 ms
    linux_rtt = re.search(
        r"=\s*([\d.]+)/([\d.]+)/([\d.]+)/",
        output,
    )

    if linux_rtt:
        min_ms = float(linux_rtt.group(1))
        avg_ms = float(linux_rtt.group(2))
        max_ms = float(linux_rtt.group(3))

    return {
        "packet_loss_percent": packet_loss,
        "min_ms": min_ms,
        "avg_ms": avg_ms,
        "max_ms": max_ms,
    }


def extract_hops_from_traceroute(output: str):
    """
    Parse robusto de traceroute:

    - mantém hops mesmo com timeout (* * *)
    - não quebra sequência
    - captura IP apenas quando disponível
    """

    import re

    hops = []

    for line in output.splitlines():
        raw = line.rstrip()
        text = raw.strip()

        if not re.match(r"^\d+\s+", text):
            continue

        # número do hop
        match = re.match(r"^(\d+)", text)
        hop_number = int(match.group(1)) if match else None

        # tenta extrair IP
        ip_matches = re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", text)
        ip = ip_matches[-1] if ip_matches else None

        # identifica timeout
        timeout = "*" in text and not ip

        hops.append({
            "hop": hop_number,
            "ip": ip,
            "hostname": None,
            "timeout": timeout,
            "raw": raw,
        })

    return hops



def tcp_connect(host: str, port: int, timeout: float = 2.0) -> Dict[str, object]:
    start = time.perf_counter()
    service = COMMON_PORT_SERVICES.get(port, "")

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "host": host,
                "port": port,
                "service": service,
                "status": "open",
                "open": True,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                "error": None,
            }

    except socket.timeout:
        return {
            "host": host,
            "port": port,
            "service": service,
            "status": "timeout",
            "open": False,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": "timeout",
        }

    except Exception as exc:
        return {
            "host": host,
            "port": port,
            "service": service,
            "status": "closed/filtered",
            "open": False,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": str(exc),
        }
    
def get_local_ip():
    """
    Descobre IP de saída da máquina (não usa hostname local)
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def get_dns_server():
    """
    Obtém servidor DNS configurado no sistema (Windows)
    """
    try:
        if sys.platform.startswith("win"):
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="ignore"
            ).stdout

            import re

            match = re.search(
                r"(?:DNS Servers|Servidores DNS|Servidor DNS)[ .:]*([\d\.]+)",
                result,
                re.IGNORECASE
            )
            if match:
                return match.group(1)

        # fallback
        return socket.gethostbyname("resolver1.opendns.com")
    except Exception:
        return None
