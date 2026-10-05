"""Сверка ключей шаблонов devops с настоящими системами и независимыми пересчётами.

bash-скрипты выполняются в bash (на Windows — Git Bash), CIDR — модуль ipaddress,
права — модуль stat, сертификаты — настоящее TLS-рукопожатие OpenSSL (cryptography + ssl),
манифесты — разбор YAML. Чего нет в окружении — тест пропускает.
"""

import datetime as dt
import ipaddress
import math
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import threading
from collections import Counter
from pathlib import Path

import pytest

from app.testing.engine.bank.devops import TEMPLATES
from app.testing.engine.templates import ItemFormat, check

REG = {t.id: t for t in TEMPLATES}


def _find_bash() -> str | None:
    candidates = [
        os.environ.get("FSP_BASH"),
        r"C:\Program Files\Git\bin\bash.exe",
        "/bin/bash",
        shutil.which("bash"),
    ]
    for c in candidates:
        if not c or not os.path.exists(c):
            continue
        low = c.lower()
        if "system32" in low or "windowsapps" in low:  # это WSL, а не bash
            continue
        try:
            out = subprocess.run([c, "-c", "echo ok"], capture_output=True, text=True, timeout=20)
        except OSError:
            continue
        if out.stdout.strip() == "ok":
            return c
    return None


BASH = _find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="bash не найден")


def _bash(script: str, cwd: Path) -> str:
    res = subprocess.run(
        [BASH, "-c", script],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
        env={**os.environ, "LC_ALL": "C"},
    )
    return res.stdout


# --------------------------------------------------------------------------- bash


@needs_bash
@pytest.mark.parametrize(
    "tid", ["devops.bash_basic_output", "devops.bash_quoting", "devops.bash_redirection"]
)
def test_bash_scripts_match_real_bash(tid, tmp_path):
    for seed in range(40):
        inst = REG[tid].generate(seed)
        work = tmp_path / str(seed)
        work.mkdir()
        out = _bash(inst.public.code, work)
        assert check(inst, out), (seed, inst.public.code, out, inst.key)


@needs_bash
def test_text_pipeline_matches_real_bash(tmp_path):
    t = REG["devops.text_pipeline"]
    for seed in range(60):
        inst = t.generate(seed)
        code = inst.public.code
        log = code.split("$ cat access.log\n")[1].split("\n$ ")[0]
        cmd = code.rsplit("\n$ ", 1)[1]
        work = tmp_path / str(seed)
        work.mkdir()
        (work / "access.log").write_text(log + "\n", encoding="utf-8", newline="\n")
        out = _bash(cmd, work)
        assert check(inst, out), (seed, cmd, out, inst.key)


@needs_bash
def test_signal_exit_codes_in_bash(tmp_path):
    from app.testing.engine.bank.devops.linux import SIGNAL_NUMBERS

    for name, num in SIGNAL_NUMBERS.items():
        out = _bash(f"set -m; sleep 30 & pid=$!; kill -s {name} $pid; wait $pid; echo $?", tmp_path)
        assert out.strip().splitlines()[-1] == str(128 + num), (name, out)
    t = REG["devops.signals"]
    for seed in range(150):
        inst = t.generate(seed)
        m = re.search(r"кодом выхода (\d+)", inst.public.prompt)
        if m:
            sig = next(k for k, v in SIGNAL_NUMBERS.items() if 128 + v == int(m.group(1)))
            assert f"SIG{sig} " in inst.public.options[inst.key]


# --------------------------------------------------------------------------- Linux


def test_chmod_with_stat_filemode():
    t = REG["devops.chmod_octal"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        if "ls -l показывает" in p:
            sym = re.search(r"права -([rwx-]{9})", p).group(1)
            mode = int(inst.key[0], 8)
            assert stat.filemode(stat.S_IFREG | mode)[1:] == sym
        elif "chmod u=" in p:
            clauses = re.search(r"chmod (u=\w*,g=\w*,o=\w*)", p).group(1)
            mode = 0
            for part, shift in zip(clauses.split(","), (6, 3, 0), strict=True):
                perms = part.split("=")[1]
                mode |= sum(b for ch, b in (("r", 4), ("w", 2), ("x", 1)) if ch in perms) << shift
            assert f"{mode:03o}" == inst.key[0]
        else:
            mode = int(re.search(r"chmod (\d{3})", p).group(1), 8)
            assert stat.filemode(stat.S_IFREG | mode)[1:] == inst.key[0]


def _stat_access(mode: int, op: str, who: str) -> bool:
    bits = {
        ("owner", "r"): stat.S_IRUSR,
        ("owner", "w"): stat.S_IWUSR,
        ("owner", "x"): stat.S_IXUSR,
        ("group", "r"): stat.S_IRGRP,
        ("group", "w"): stat.S_IWGRP,
        ("group", "x"): stat.S_IXGRP,
        ("other", "r"): stat.S_IROTH,
        ("other", "w"): stat.S_IWOTH,
        ("other", "x"): stat.S_IXOTH,
    }
    if who == "root":
        return op != "x" or bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    return bool(mode & bits[(who, op)])


def test_file_access_recomputed_with_stat():
    t = REG["devops.file_access"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        sym = re.search(r"-([rwx-]{9}) 1", p).group(1)
        mode = sum(1 << (8 - i) for i, ch in enumerate(sym) if ch != "-")
        assert stat.filemode(stat.S_IFREG | mode)[1:] == sym
        op = "r" if "прочитать" in p else "w" if "записать" in p else "x"
        expected = set()
        for i, opt in enumerate(inst.public.options):
            who = (
                "root"
                if opt == "root"
                else "owner"
                if "владелец файла" in opt
                else "other"
                if "не владелец" in opt
                else "group"
            )
            if _stat_access(mode, op, who):
                expected.add(i)
        assert expected == inst.key, (seed, sym, op, inst.public.options)


# --------------------------------------------------------------------------- сети


def test_ports_match_services_database():
    names = {
        "SSH": "ssh",
        "HTTP": "http",
        "HTTPS": "https",
        "DNS": "domain",
        "SMTP": "smtp",
        "FTP": "ftp",
        "PostgreSQL": "postgresql",
        "MySQL": "mysql",
    }
    checked = 0
    t = REG["devops.well_known_ports"]
    for seed in range(200):
        inst = t.generate(seed)
        svc = next((k for k in names if k in inst.public.prompt.split("Ответ")[0]), None)
        if svc is None or (svc == "HTTP" and "HTTPS" in inst.public.prompt):
            continue
        try:
            port = socket.getservbyname(names[svc], "tcp")
        except OSError:
            continue
        assert check(inst, str(port)), (svc, inst.key)
        checked += 1
    assert checked >= 20


def test_cidr_counts_with_ipaddress():
    t = REG["devops.cidr_hosts_count"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        if "Нужна одна подсеть" in p:
            hosts = int(re.search(r"минимум на (\d+)", p).group(1))
            best = max(
                pr
                for pr in range(8, 31)
                if ipaddress.ip_network(f"10.0.0.0/{pr}").num_addresses - 2 >= hosts
            )
            assert inst.key.value == best
            continue
        net = ipaddress.ip_network(re.search(r"(\d+\.\d+\.\d+\.\d+/\d+)", p).group(1))
        if "разбить" in p:
            m = int(re.search(r"подсетей /(\d+)", p).group(1))
            value = len(list(net.subnets(new_prefix=m)))
        elif "выдать хостам" in p:
            value = len(list(net.hosts()))
        else:
            value = net.num_addresses
        assert inst.key.value == value, p


def test_subnet_overlap_with_ipaddress():
    t = REG["devops.subnet_overlap"]
    for seed in range(200):
        inst = t.generate(seed)
        vpc = ipaddress.ip_network(re.search(r"блоком (\S+),", inst.public.prompt).group(1))
        existing = [
            ipaddress.ip_network(line.split(": ")[1]) for line in inst.public.code.split("\n")
        ]
        expected = set()
        for i, opt in enumerate(inst.public.options):
            net = ipaddress.ip_network(opt)
            if net.subnet_of(vpc) and not any(net.overlaps(e) for e in existing):
                expected.add(i)
        assert expected == inst.key, seed


def _make_cert(cn: str, sans: list[str], tmp: Path):
    x509 = pytest.importorskip("cryptography.x509")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    (tmp / "cert.pem").write_bytes(pem)
    (tmp / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return pem.decode()


def _serve_tls(tmp: Path):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(tmp / "cert.pem", tmp / "key.pem")
    sock = socket.create_server(("127.0.0.1", 0))
    stop = threading.Event()

    def loop():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except (TimeoutError, OSError):
                continue
            try:
                with ctx.wrap_socket(conn, server_side=True):
                    pass
            except (ssl.SSLError, OSError):
                pass

    threading.Thread(target=loop, daemon=True).start()
    return sock, stop


def test_tls_san_with_real_handshake(tmp_path):
    pytest.importorskip("cryptography")
    t = REG["devops.tls_san_match"]
    for seed in range(25):
        inst = t.generate(seed)
        code = inst.public.code
        cn = re.search(r"CN = (\S+)", code).group(1)
        sans = re.findall(r"DNS:([^,\s]+)", code)
        work = tmp_path / str(seed)
        work.mkdir()
        pem = _make_cert(cn, sans, work)
        sock, stop = _serve_tls(work)
        port = sock.getsockname()[1]
        try:
            ok = set()
            for i, opt in enumerate(inst.public.options):
                host = opt.removeprefix("https://").rstrip("/")
                ctx = ssl.create_default_context(cadata=pem)
                ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
                with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
                    try:
                        with ctx.wrap_socket(raw, server_hostname=host):
                            ok.add(i)
                    except ssl.SSLCertVerificationError:
                        pass
        finally:
            stop.set()
            sock.close()
        assert ok == inst.key, (seed, sans, cn, inst.public.options)


# --------------------------------------------------------------------------- Kubernetes


def _cpu(q: str) -> int:
    return round(float(q[:-1]) if q.endswith("m") else float(q) * 1000)


def _mem(q: str) -> int:
    units = {"Mi": 1, "Gi": 1024}
    return int(q[:-2]) * units[q[-2:]]


def test_k8s_resources_recomputed():
    t = REG["devops.k8s_resources"]
    for seed in range(200):
        inst = t.generate(seed)
        c = inst.public.code
        cpus = re.findall(r'cpu:\s+"?([\d.]+m?)"?', c)
        mems = re.findall(r'memory:\s+"?(\d+[MG]i)"?', c)
        alloc_cpu, used_cpu, req_cpu, _ = cpus
        alloc_mem, used_mem, req_mem, _ = mems
        value = min(
            (_cpu(alloc_cpu) - _cpu(used_cpu)) // _cpu(req_cpu),
            (_mem(alloc_mem) - _mem(used_mem)) // _mem(req_mem),
        )
        assert inst.key.value == value, (seed, c)


def test_k8s_rollout_recomputed():
    t = REG["devops.k8s_rollout"]
    for seed in range(200):
        inst = t.generate(seed)
        c = inst.public.code
        r = int(re.search(r"replicas: (\d+)", c).group(1))
        surge = re.search(r'maxSurge: "?(\d+%?)"?', c).group(1)
        unav = re.search(r'maxUnavailable: "?(\d+%?)"?', c).group(1)

        def val(x, up, r=r):
            if x.endswith("%"):
                return (math.ceil if up else math.floor)(int(x[:-1]) * r / 100)
            return int(x)

        s, u = val(surge, True), val(unav, False)
        assert (s, u) != (0, 0)
        value = r + s if "наибольшее" in inst.public.prompt else r - u
        assert inst.key.value == value, (seed, c)


def test_k8s_manifest_bug_detected_from_yaml():
    yaml = pytest.importorskip("yaml")
    t = REG["devops.k8s_manifest_bug"]
    for seed in range(150):
        inst = t.generate(seed)
        dep, svc = yaml.safe_load_all(inst.public.code)
        tpl_labels = dep["spec"]["template"]["metadata"]["labels"]
        container = dep["spec"]["template"]["spec"]["containers"][0]
        port = container["ports"][0]["containerPort"]
        res = container["resources"]
        problems = []
        if dep["spec"]["selector"]["matchLabels"] != tpl_labels:
            problems.append("app:")
        if container["readinessProbe"]["httpGet"]["port"] != port:
            problems.append("port:")
        if _mem(res["limits"]["memory"]) < _mem(res["requests"]["memory"]):
            problems.append("memory:")
        if svc["spec"]["selector"] != tpl_labels:
            problems.append("app:")
        if svc["spec"]["ports"][0]["targetPort"] != port:
            problems.append("targetPort:")
        assert len(problems) == 1, (seed, problems)
        line = inst.public.code.split("\n")[inst.key - 1].strip()
        assert line.startswith(problems[0]), (seed, line, problems)


# --------------------------------------------------------------------------- SLO, semver, plan


def test_error_budget_and_burn_rate_recomputed():
    for seed in range(200):
        inst = REG["devops.error_budget"].generate(seed)
        p = inst.public.prompt
        slo = float(re.search(r"(\d+(?:\.\d+)?)%", p).group(1))
        days = int(re.search(r"(\d+) дней", p).group(1))
        budget = days * 1440 * (1 - slo / 100)
        if "минут полного простоя" in p:
            value = budget
        elif "осталась" in p:
            spent = float(re.search(r"было (\d+(?:\.\d+)?) мин", p).group(1))
            value = 100 * (budget - spent) / budget
        else:
            total = int(re.search(r"Ожидается ([\d ]+) запросов", p).group(1).replace(" ", ""))
            value = round(total * (1 - slo / 100))
        assert abs(inst.key.value - value) < 1e-6, p

        inst = REG["devops.burn_rate"].generate(seed)
        p = inst.public.prompt
        slo = float(re.search(r"SLO: (\d+(?:\.\d+)?)%", p).group(1))
        err = float(re.search(r"ошибок — (\d+(?:\.\d+)?)%", p).group(1))
        burn = (err / 100) / (1 - slo / 100)
        if "burn rate" in p:
            value = burn
        elif "часов" in p:
            value = 30 * 24 / burn
        else:
            value = 100 * burn / (30 * 24)
        assert abs(inst.key.value - value) < 1e-6, p


def test_semver_with_packaging():
    version = pytest.importorskip("packaging.version")
    t = REG["devops.semver_bump"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        old = version.Version(re.search(r"версии (\d+\.\d+\.\d+)", p).group(1))
        new = version.Version(inst.key[0])
        if "удалён" in p or "теперь обязательный" in p:
            assert (new.major, new.minor, new.micro) == (old.major + 1, 0, 0)
        elif "добавлен" in p:
            assert (new.major, new.minor, new.micro) == (old.major, old.minor + 1, 0)
        else:
            assert (new.major, new.minor, new.micro) == (old.major, old.minor, old.micro + 1)


def _parse_hcl(text: str) -> dict[str, tuple[int, dict[str, str]]]:
    out = {}
    for m in re.finditer(r'resource "(\w+)" "(\w+)" \{\n(.*?)\n\}', text, re.S):
        attrs = dict(
            line.strip().split(" = ", 1) for line in m.group(3).split("\n") if line.strip()
        )
        count = int(attrs.pop("count", "1"))
        out[f"{m.group(1)}.{m.group(2)}"] = (count, attrs)
    return out


def test_terraform_plan_recomputed():
    force_new = {"ami", "bucket", "cidr_block", "engine"}
    t = REG["devops.terraform_plan"]
    for seed in range(200):
        inst = t.generate(seed)
        old_text, new_text = inst.public.code.split("# Новая версия конфигурации:")
        old, new = _parse_hcl(old_text), _parse_hcl(new_text)
        add = change = destroy = 0
        for addr in old.keys() | new.keys():
            oc, oa = old.get(addr, (0, {}))
            nc, na = new.get(addr, (0, {}))
            common = min(oc, nc)
            diff = {k for k in oa.keys() | na.keys() if oa.get(k) != na.get(k)}
            if common and diff & force_new:
                add += common
                destroy += common
            elif common and diff:
                change += common
            add += max(0, nc - oc)
            destroy += max(0, oc - nc)
        assert check(inst, f"{add} {change} {destroy}"), (seed, inst.key, add, change, destroy)


def test_bank_composition():
    assert len(TEMPLATES) == 30
    grades = Counter(t.target_grade for t in TEMPLATES)
    assert grades == {"intern": 6, "junior": 8, "middle": 9, "senior": 7}
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6 and max(topics.values()) <= 7
    assert {t.format for t in TEMPLATES} == set(ItemFormat)
