"""DevOps — сети: порты, размеры подсетей, DNS-записи, пересечение подсетей, SAN в TLS."""

from __future__ import annotations

import random

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)

# --------------------------------------------------------------------------- порты

PORTS = {
    "SSH": 22,
    "HTTP": 80,
    "HTTPS": 443,
    "DNS": 53,
    "SMTP": 25,
    "FTP (управляющее соединение)": 21,
    "PostgreSQL": 5432,
    "MySQL": 3306,
    "Redis": 6379,
    "MongoDB": 27017,
    "RDP": 3389,
    "Kubernetes API server": 6443,
}


def _gen_ports(rng: random.Random) -> Variant:
    service = rng.choice(tuple(PORTS))
    host = rng.choice(("db-01", "web-03", "bastion", "k8s-master", "mail", "cache-02"))
    net = rng.choice(("10.0.5.0/24", "172.20.0.0/16", "192.168.10.0/24", "10.8.0.0/20"))
    templates = (
        f"На сервере {host} нужно открыть в firewall порт для {service} (порт по умолчанию) "
        f"из сети {net}. Какой порт указать?",
        f"Сканер показал, что на {host} открыт стандартный порт {service}. Какой это номер порта?",
        f"В группе безопасности облака для {host} нужно разрешить входящий трафик {service} "
        f"с адресов {net}. Какой TCP/UDP-порт по умолчанию?",
        f"Вы пишете readiness-проверку «порт открыт» для {service} на {host} с настройками "
        "по умолчанию. Какой порт проверять?",
    )
    return Variant(
        prompt=rng.choice(templates) + " Ответ — число.",
        key=(str(PORTS[service]),),
        extra={"answer_type": "text", "max_length": 6},
        explanation=f"{service}: {PORTS[service]}",
    )


PORTS_T = ItemTemplate(
    id="devops.well_known_ports",
    specialization="devops",
    topic="networking",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_ports,
    a=1.0,
    b=-1.7,
    title="Стандартные порты сервисов",
    time_limit_s=60,
)

# --------------------------------------------------------------------------- размер подсетей


def _gen_cidr_count(rng: random.Random) -> Variant:
    q = rng.choice(("hosts", "subnets", "prefix_for_hosts", "addresses"))
    base = rng.choice(("10.20.0.0", "172.16.0.0", "192.168.0.0", "10.0.0.0"))
    if q == "hosts":
        p = rng.randint(20, 30)
        value = 2 ** (32 - p) - 2
        ask = (
            f"Сколько адресов можно выдать хостам в подсети {base}/{p} "
            "(без адреса сети и broadcast)?"
        )
    elif q == "addresses":
        p = rng.randint(16, 28)
        value = 2 ** (32 - p)
        ask = f"Сколько всего IPv4-адресов в блоке {base}/{p}?"
    elif q == "subnets":
        p = rng.randint(16, 24)
        m = p + rng.randint(1, 6)
        value = 2 ** (m - p)
        ask = f"На сколько подсетей /{m} можно разбить сеть {base}/{p}?"
    else:
        hosts = rng.randint(3, 4000)
        p = 30
        while 2 ** (32 - p) - 2 < hosts:
            p -= 1
        value = p
        ask = (
            f"Нужна одна подсеть минимум на {hosts} хостов (адрес сети и broadcast выдавать "
            "нельзя). Какой самый длинный префикс подойдёт? Ответ — число после «/»."
        )
    return Variant(
        prompt=ask,
        key=NumericKey(value, 0),
        extra={"answer_type": "integer"},
        explanation=f"Ответ: {value}",
    )


CIDR_COUNT = ItemTemplate(
    id="devops.cidr_hosts_count",
    specialization="devops",
    topic="networking",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_cidr_count,
    a=1.3,
    b=-0.3,
    title="Размеры подсетей CIDR",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- DNS-записи

_RECORDS = ("A", "AAAA", "CNAME", "MX", "TXT", "NS", "PTR", "SRV", "CAA")


def _gen_dns(rng: random.Random) -> Variant:
    d = rng.choice(("shop.ru", "fsp-talent.ru", "example.com", "company.local"))
    octets = (rng.choice((31, 77, 95, 185)), rng.randint(0, 255), rng.randint(0, 255))
    ip4 = ".".join(map(str, octets)) + f".{rng.randint(1, 254)}"
    ip6 = f"2a02:6b8:{rng.randint(1, 9999):x}::{rng.randint(1, 255):x}"
    sub = rng.choice(("api", "app", "status", "cdn", "docs"))
    scenarios = [
        (f"Домен {sub}.{d} должен указывать на IPv4-адрес сервера {ip4}.", "A"),
        (f"Домен {sub}.{d} должен открываться по IPv6-адресу {ip6}.", "AAAA"),
        (
            f"{sub}.{d} должен быть псевдонимом для {d.split('.')[0]}.cdn-provider.net, чей адрес "
            "провайдер меняет сам.",
            "CNAME",
        ),
        (
            f"Почта для адресов вида user@{d} должна приходить на mx{rng.randint(1, 3)}.mail.ru.",
            "MX",
        ),
        (
            f"Сервис требует подтвердить владение доменом {d}, разместив строку "
            f"verification={rng.randint(10**7, 10**8)} в DNS.",
            "TXT",
        ),
        (f"Нужно делегировать зону {sub}.{d} на DNS-серверы другой команды.", "NS"),
        (f"Почтовый сервер с адресом {ip4} должен иметь обратную запись (адрес → имя).", "PTR"),
        (f"Клиенты должны находить сервис _sip._tcp.{d}: порт 5060 и хост с приоритетом.", "SRV"),
        (
            f"Нужно разрешить выпуск сертификатов для {d} только центру сертификации "
            "Let's Encrypt.",
            "CAA",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text} Какую DNS-запись нужно создать?",
        correct,
        [r for r in _RECORDS if r != correct],
        explanation=f"Тип записи: {correct}",
    )


DNS = ItemTemplate(
    id="devops.dns_records",
    specialization="devops",
    topic="networking",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_dns,
    a=1.1,
    b=-0.7,
    title="Тип DNS-записи под задачу",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- пересечение подсетей


def ip_to_int(ip: str) -> int:
    a, b, c, d = (int(x) for x in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(v: int) -> str:
    return ".".join(str((v >> s) & 255) for s in (24, 16, 8, 0))


def block_range(cidr: str) -> tuple[int, int]:
    ip, p = cidr.split("/")
    size = 2 ** (32 - int(p))
    start = ip_to_int(ip) & ~(size - 1) & 0xFFFFFFFF
    return start, start + size - 1


def _rand_block(rng: random.Random, vpc_start: int, vpc_size: int, prefix: int) -> str:
    size = 2 ** (32 - prefix)
    start = vpc_start + rng.randrange(vpc_size // size) * size
    return f"{int_to_ip(start)}/{prefix}"


def _gen_overlap(rng: random.Random) -> Variant:
    second = rng.randint(0, 250)
    vpc = rng.choice((f"10.{second}.0.0/16", f"172.{rng.randint(16, 31)}.0.0/16"))
    vs, ve = block_range(vpc)
    size = ve - vs + 1
    while True:
        existing = []
        for _ in range(rng.randint(2, 3)):
            existing.append(_rand_block(rng, vs, size, rng.choice((20, 22, 24))))
        ranges = [block_range(c) for c in existing]
        if any(
            a[0] <= b[1] and b[0] <= a[1] for i, a in enumerate(ranges) for b in ranges[i + 1 :]
        ):
            continue
        cands: list[str] = []
        for _ in range(5):
            r = rng.random()
            if r < 0.15:  # вне VPC
                cands.append(
                    f"10.{(second + 1) % 256}.{rng.randrange(0, 256, 4)}.0/22"
                    if vpc.startswith("10.")
                    else f"192.168.{rng.randint(0, 255)}.0/24"
                )
            elif r < 0.5:  # внутри существующей
                ex = rng.choice(existing)
                es, ee = block_range(ex)
                p = int(ex.split("/")[1]) + rng.randint(0, 3)
                cands.append(_rand_block(rng, es, ee - es + 1, min(p, 28)))
            else:
                cands.append(_rand_block(rng, vs, size, rng.choice((19, 21, 23, 24, 26))))
        if len(set(cands)) < 5:
            continue

        def ok(c: str, ranges: list[tuple[int, int]] = ranges) -> bool:
            s, e = block_range(c)
            inside = vs <= s and e <= ve
            free = all(e < a or s > b for a, b in ranges)
            return inside and free

        good = [c for c in cands if ok(c)]
        if 1 <= len(good) <= 4:
            break
    listing = "\n".join(f"subnet-{i + 1}: {c}" for i, c in enumerate(existing))
    return make_multi_choice(
        rng,
        f"VPC с блоком {vpc}, в нём уже есть подсети (ниже). Новая подсеть должна целиком "
        "лежать внутри VPC и не пересекаться с существующими. Какие из предложенных подсетей "
        "можно создать (каждую рассматривайте отдельно)?",
        good,
        [c for c in cands if c not in good],
        code=listing,
        extra={"min_choices": 1},
        explanation="Подходят: " + ", ".join(good),
    )


SUBNET_OVERLAP = ItemTemplate(
    id="devops.subnet_overlap",
    specialization="devops",
    topic="networking",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_overlap,
    a=1.4,
    b=0.5,
    title="Можно ли создать подсеть в VPC",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- SAN в сертификате


def san_matches(pattern: str, host: str) -> bool:
    """Сопоставление имени по RFC 6125: «*» — только целая левая метка, одна метка."""
    p, h = pattern.lower().split("."), host.lower().split(".")
    if len(p) != len(h):
        return False
    if p[0] == "*":
        return p[1:] == h[1:] and h[0] != ""
    return p == h


def _gen_san(rng: random.Random) -> Variant:
    d = rng.choice(("shop.ru", "fsp-talent.ru", "example.com", "bank.test"))
    other = rng.choice(("cdn-shop.net", "partner.org", "static.io"))
    sub = rng.choice(("api", "admin", "app", "pay"))
    sans = [f"*.{d}"]
    if rng.random() < 0.5:
        sans.append(d)
    if rng.random() < 0.5:
        sans.append(f"{sub}.{other}")
    cn = rng.choice((f"legacy.{other}", f"www.{other}", f"old.{d}.local"))
    while True:
        hosts = {
            d,
            f"www.{d}",
            f"{sub}.{d}",
            f"v2.{sub}.{d}",
            f"{sub}.{other}",
            cn,
            f"{sub.upper()}.{d.upper()}",
            f"{sub}-{d.split('.')[0]}.{d.split('.')[1]}",
        }
        hosts_list = sorted(hosts)
        rng.shuffle(hosts_list)
        hosts_list = hosts_list[:6]
        good = [h for h in hosts_list if any(san_matches(s, h) for s in sans)]
        if 1 <= len(good) <= 4:
            break
    cert = "\n".join(
        [
            f"Subject: CN = {cn}",
            "X509v3 Subject Alternative Name:",
            "    " + ", ".join(f"DNS:{s}" for s in sans),
            "Срок действия: сертификат действителен сейчас, цепочка доверенная",
        ]
    )
    return make_multi_choice(
        rng,
        "Сервер отдаёт сертификат (фрагмент openssl x509 -text ниже). Для каких имён "
        "современный браузер или curl примет его без ошибки проверки имени хоста? "
        "Отметьте все.",
        [f"https://{h}/" for h in good],
        [f"https://{h}/" for h in hosts_list if h not in good],
        code=cert,
        extra={"min_choices": 1},
        explanation="Подходят: " + ", ".join(good),
    )


TLS_SAN = ItemTemplate(
    id="devops.tls_san_match",
    specialization="devops",
    topic="networking",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_san,
    a=1.4,
    b=1.2,
    title="Подойдёт ли сертификат к имени хоста",
    time_limit_s=180,
)

TEMPLATES = [PORTS_T, CIDR_COUNT, DNS, SUBNET_OVERLAP, TLS_SAN]
