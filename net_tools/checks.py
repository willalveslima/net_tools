from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional

from .utils import (
    extract_hops_from_traceroute,
    get_dns_server,
    get_local_ip,
    is_ip_address,
    normalize_target,
    parse_ping_summary,
    ping_command,
    resolve_dns,
    reverse_dns,
    run_command,
    tcp_connect,
    traceroute_command,
)


def dns_test(target: str) -> Dict[str, object]:
    """
    Executa resolução DNS do destino.
    """
    return resolve_dns(target)


def dns_query_all(target: str) -> Dict[str, list]:
    """
    Executa consultas avançadas de DNS para múltiplos tipos de registros.
    """
    record_types = ["A", "AAAA", "MX", "TXT", "CNAME", "NS", "SOA"]
    results = {}

    try:
        import dns.resolver
    except ImportError:
        # Fallback caso dnspython não esteja instalado no ambiente virtual
        simple = resolve_dns(target)
        if simple.get("success"):
            return {
                "A": [{"Valor": addr} for addr in simple.get("addresses", [])],
                "_warning": ["Instale a biblioteca dnspython para obter mais registros DNS."]
            }
        return {"error": ["dnspython não instalado e resolução simples falhou."]}

    resolver = dns.resolver.Resolver()
    resolver.timeout = 2.0
    resolver.lifetime = 2.0

    for rtype in record_types:
        results[rtype] = []
        try:
            answers = resolver.resolve(target, rtype)
            for rdata in answers:
                if rtype == "MX":
                    results[rtype].append({
                        "Preferência": rdata.preference,
                        "Servidor": str(rdata.exchange).rstrip(".")
                    })
                elif rtype == "SOA":
                    results[rtype].append({
                        "MName": str(rdata.mname).rstrip("."),
                        "RName": str(rdata.rname).rstrip("."),
                        "Serial": rdata.serial,
                        "Refresh": rdata.refresh,
                        "Retry": rdata.retry,
                        "Expire": rdata.expire,
                        "Minimum": rdata.minimum
                    })
                elif rtype == "TXT":
                    val = "".join(b.decode('utf-8', errors='ignore') for b in rdata.strings)
                    results[rtype].append({"Valor": val})
                else:
                    results[rtype].append({"Valor": str(rdata).rstrip(".")})
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            continue
        except dns.resolver.NXDOMAIN:
            results["error"] = [{"Erro": f"Domínio {target} não encontrado (NXDOMAIN)."}]
            break
        except Exception as e:
            results[rtype].append({"Erro": str(e)})

    return results


def ping_test(
    target: str,
    count: int = 4,
    timeout_ms: int = 1000,
) -> Dict[str, object]:
    """
    Executa ping no destino e retorna saída bruta + estatísticas estruturadas.
    """
    result = run_command(
        ping_command(
            target,
            count=count,
            timeout_ms=timeout_ms,
        ),
        timeout=max(5, count * 2),
    )

    result["summary"] = parse_ping_summary(result.get("stdout", ""))

    return result


def resolve_hop_names(
    hops: List[Dict[str, object]],
    max_workers: int = 8,
    timeout: float = 2.0,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Dict[str, object]]:
    """
    Resolve nomes reversos dos hops em paralelo.

    Mantém os hops mesmo quando não houver IP ou quando não houver PTR.
    """
    if not hops:
        return []

    resolved_by_hop = {hop.get("hop"): dict(hop) for hop in hops}
    resolvable_hops = [hop for hop in hops if hop.get("ip")]

    total = len(resolvable_hops)

    if total == 0:
        return sorted(
            resolved_by_hop.values(),
            key=lambda item: item.get("hop") or 999,
        )

    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(reverse_dns, hop["ip"], timeout): hop
            for hop in resolvable_hops
        }

        for future in as_completed(futures):
            hop = futures[future]
            hostname = future.result()

            new_hop = dict(hop)
            new_hop["hostname"] = hostname

            resolved_by_hop[hop.get("hop")] = new_hop

            completed += 1

            if progress_callback:
                progress_callback(
                    completed,
                    total,
                    f"Resolvendo nome do hop {hop.get('ip')}",
                )

    return sorted(
        resolved_by_hop.values(),
        key=lambda item: item.get("hop") or 999,
    )


def traceroute_test(
    target: str,
    max_hops: int = 30,
    resolve_names: bool = True,
    reverse_dns_timeout_s: float = 2.0,
    max_workers: int = 8,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, object]:
    """
    Executa tracert/traceroute.

    O comando é executado em modo numérico para ser mais rápido:
    - Windows: tracert -d
    - Linux: traceroute -n

    Depois, se habilitado, resolve os hostnames dos hops em paralelo.
    """
    result = run_command(
        traceroute_command(
            target,
            max_hops=max_hops,
        ),
        timeout=60,
    )

    hops = extract_hops_from_traceroute(result.get("stdout", ""))

    if resolve_names:
        hops = resolve_hop_names(
            hops,
            max_workers=max_workers,
            timeout=reverse_dns_timeout_s,
            progress_callback=progress_callback,
        )

    result["hops"] = hops

    # Gravação do caminho descoberto no banco de dados do mapa de rede
    try:
        from .db import save_traceroute_path
        from .utils import get_local_ip
        local_ip = get_local_ip()
        save_traceroute_path(local_ip, hops, target)
    except Exception:
        pass

    return result


def mtr_like_test(
    hops: List[Dict[str, object]],
    count_per_hop: int = 3,
    timeout_ms: int = 1000,
    max_workers: int = 8,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Dict[str, object]]:
    """
    Executa ping em paralelo para cada hop.

    Retorna estatísticas por hop:
    - perda
    - mínimo
    - média
    - máximo
    - timeout
    - hostname
    """
    valid_hops = [hop for hop in hops if hop.get("ip")]

    total = len(valid_hops)

    results: List[Dict[str, object]] = []

    if total == 0:
        return results

    def worker(hop: Dict[str, object]) -> Dict[str, object]:
        ip = hop["ip"]

        ping = ping_test(
            ip,
            count=count_per_hop,
            timeout_ms=timeout_ms,
        )

        summary = ping.get("summary", {})

        return {
            "hop": hop.get("hop"),
            "ip": ip,
            "hostname": hop.get("hostname"),
            "packet_loss_percent": summary.get("packet_loss_percent"),
            "min_ms": summary.get("min_ms"),
            "avg_ms": summary.get("avg_ms"),
            "max_ms": summary.get("max_ms"),
            "timeout": ping.get("timeout", False),
            "raw_hop": hop.get("raw"),
            "stdout": ping.get("stdout", ""),
            "stderr": ping.get("stderr", ""),
        }

    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, hop): hop
            for hop in valid_hops
        }

        for future in as_completed(futures):
            data = future.result()
            results.append(data)

            completed += 1

            if progress_callback:
                label = data.get("hostname") or data.get("ip")

                progress_callback(
                    completed,
                    total,
                    f"MTR-like: testando {label}",
                )

    return sorted(
        results,
        key=lambda item: item.get("hop") or 999,
    )


def tcp_port_test(
    target: str,
    ports: List[int],
    timeout: float = 2.0,
    max_workers: int = 10,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Dict[str, object]]:
    """
    Testa portas TCP em paralelo.

    Equivalente funcional a um teste básico de telnet/nc.
    """
    results: List[Dict[str, object]] = []
    total = len(ports)

    if not ports:
        return results

    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                tcp_connect,
                target,
                port,
                timeout,
            ): port
            for port in ports
        }

        for future in as_completed(futures):
            data = future.result()
            results.append(data)

            completed += 1

            if progress_callback:
                progress_callback(
                    completed,
                    total,
                    f"TCP: testando porta {data.get('port')}",
                )

    return sorted(
        results,
        key=lambda item: item["port"],
    )


def run_all_tests(
    target: str,
    tcp_ports: Optional[List[int]] = None,
    ping_count: int = 4,
    mtr_ping_count: int = 3,
    timeout_ms: int = 1000,
    tcp_timeout_s: float = 2.0,
    reverse_dns_timeout_s: float = 2.0,
    max_hops: int = 30,
    max_workers: int = 8,
    resolve_hop_hostnames: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, object]:
    """
    Executa o teste completo:

    - IP de origem
    - DNS server identificado
    - DNS do destino, se entrada não for IP
    - Ping do destino
    - Traceroute com hostnames
    - MTR-like por hop
    - TCP ports
    """
    target = normalize_target(target)
    is_ip = is_ip_address(target)

    output: Dict[str, object] = {
        "target": target,
        "is_ip": is_ip,

        # Informações do ambiente de origem
        "origin_ip": get_local_ip(),
        "dns_server": get_dns_server(),

        # Resultados dos testes
        "dns": None,
        "ping": None,
        "traceroute": None,
        "hops": [],
        "mtr": [],
        "tcp": [],
    }

    total_steps = 5 if not is_ip else 4
    step = 0

    # DNS do destino
    if not is_ip:
        step += 1

        if progress_callback:
            progress_callback(
                step,
                total_steps,
                "Executando DNS do destino",
            )

        output["dns"] = dns_test(target)

    # Ping do destino
    step += 1

    if progress_callback:
        progress_callback(
            step,
            total_steps,
            "Executando ping do destino",
        )

    output["ping"] = ping_test(
        target,
        count=ping_count,
        timeout_ms=timeout_ms,
    )

    # Traceroute
    step += 1

    if progress_callback:
        progress_callback(
            step,
            total_steps,
            "Executando traceroute",
        )

    output["traceroute"] = traceroute_test(
        target,
        max_hops=max_hops,
        resolve_names=resolve_hop_hostnames,
        reverse_dns_timeout_s=reverse_dns_timeout_s,
        max_workers=max_workers,
        progress_callback=None,
    )

    output["hops"] = output["traceroute"].get("hops", [])

    # MTR-like
    step += 1

    if progress_callback:
        progress_callback(
            step,
            total_steps,
            "Executando MTR-like",
        )

    output["mtr"] = mtr_like_test(
        output["hops"],
        count_per_hop=mtr_ping_count,
        timeout_ms=timeout_ms,
        max_workers=max_workers,
        progress_callback=None,
    )

    # TCP
    step += 1

    if progress_callback:
        progress_callback(
            step,
            total_steps,
            "Executando portas TCP",
        )

    output["tcp"] = tcp_port_test(
        target,
        ports=tcp_ports or [],
        timeout=tcp_timeout_s,
        max_workers=max_workers,
        progress_callback=None,
    )

    return output


def subnet_scan_test(
    cidr: str,
    timeout_ms: int = 300,
    max_workers: int = 50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Dict[str, object]]:
    """
    Varre uma subrede CIDR em busca de hosts ativos respondendo a PING (ICMP).
    Resolve hostnames reverso em paralelo para os hosts ativos encontrados.
    """
    import ipaddress

    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except Exception as e:
        raise ValueError(f"Subrede CIDR inválida: {cidr}. Erro: {e}")

    hosts = [str(ip) for ip in network.hosts()]
    total_hosts = len(hosts)

    if total_hosts == 0:
        return []

    active_hosts = []

    # 1. Função executora para testar cada IP de forma assíncrona
    def test_single_ip(ip_str: str) -> Optional[Dict[str, object]]:
        # Envia 1 pacote de ping com timeout curto
        ping = ping_test(ip_str, count=1, timeout_ms=timeout_ms)
        summary = ping.get("summary", {})
        loss = summary.get("packet_loss_percent")

        # Se perda < 100%, o host respondeu
        if loss is not None and loss < 100:
            avg_ms = summary.get("avg_ms") or 0.0
            # Resolve DNS reverso para o host ativo
            hostname = reverse_dns(ip_str, timeout=1.0)
            return {
                "ip": ip_str,
                "hostname": hostname or "",
                "latency_ms": avg_ms
            }
        return None

    # 2. Executar em paralelo usando ThreadPoolExecutor
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_ip, ip): ip for ip in hosts}

        for future in as_completed(futures):
            res = future.result()
            if res:
                active_hosts.append(res)

            completed += 1
            if progress_callback:
                progress_callback(
                    completed,
                    total_hosts,
                    f"Escaneando IP {futures[future]}"
                )

    # Retorna ordenado pelo IP
    return sorted(active_hosts, key=lambda x: ipaddress.ip_address(x["ip"]))

