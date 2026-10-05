"""DevOps — Kubernetes: probes, адреса сервисов, ресурсы, ошибки манифеста, rolling update."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

_APPS = ("orders", "billing", "catalog", "auth", "notify", "search")

# --------------------------------------------------------------------------- probes

_PROBE_ANSWERS = {
    "ready_fail": "Под убирается из Endpoints сервиса и не получает трафик; контейнер "
    "не перезапускается",
    "live_fail": "kubelet перезапускает контейнер",
    "startup": "Добавить startupProbe: пока она не прошла, liveness и readiness не выполняются",
    "use_ready": "Использовать readinessProbe: под временно не получает трафик, но не "
    "перезапускается",
    "nothing": "Ничего не происходит, пробы влияют только на метрики",
    "reschedule": "Под удаляется и создаётся заново на другой ноде",
}


def _gen_probes(rng: random.Random) -> Variant:
    app = rng.choice(_APPS)
    n = rng.choice((3, 5, 6))
    sec = rng.choice((60, 90, 120, 180))
    scenarios = [
        (
            f"У контейнера {app} readinessProbe не проходит {n} раз подряд "
            f"(failureThreshold: {n}). "
            "Что произойдёт?",
            "ready_fail",
            ["live_fail", "nothing", "reschedule"],
        ),
        (
            f"У контейнера {app} livenessProbe не проходит {n} раз подряд (failureThreshold: {n}). "
            "Что произойдёт?",
            "live_fail",
            ["ready_fail", "nothing", "reschedule"],
        ),
        (
            f"Сервис {app} на JVM стартует до {sec} с, а livenessProbe начинает проверять его "
            "через 10 с и убивает контейнер раньше, чем он поднимется. Как правильно исправить?",
            "startup",
            ["use_ready", "nothing", "reschedule"],
        ),
        (
            f"Под {app} при старте {sec} с прогревает кэш; в это время запросы к нему падают, но "
            "перезапуск не нужен. Какую пробу использовать, чтобы трафик не шёл в под?",
            "use_ready",
            ["live_fail", "startup", "nothing"],
        ),
    ]
    text, correct, wrong = rng.choice(scenarios)
    return make_single_choice(
        rng,
        text,
        _PROBE_ANSWERS[correct],
        [_PROBE_ANSWERS[w] for w in wrong],
        explanation=f"Верно: {_PROBE_ANSWERS[correct]}",
    )


PROBES = ItemTemplate(
    id="devops.k8s_probes",
    specialization="devops",
    topic="kubernetes",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_probes,
    a=1.2,
    b=-0.3,
    title="Liveness, readiness и startup probes",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- адрес сервиса


def _gen_service_port(rng: random.Random) -> Variant:
    app = rng.choice(_APPS)
    ns = rng.choice(("prod", "shop", "payments", "team-a"))
    port, target, node = (
        rng.choice((80, 8000, 9000, 443)),
        rng.choice((8080, 3000, 5000)),
        rng.randint(30000, 32767),
    )
    code = "\n".join(
        [
            "apiVersion: v1",
            "kind: Service",
            "metadata:",
            f"  name: {app}",
            f"  namespace: {ns}",
            "spec:",
            "  type: NodePort",
            "  selector:",
            f"    app: {app}",
            "  ports:",
            f"    - port: {port}",
            f"      targetPort: {target}",
            f"      nodePort: {node}",
        ]
    )
    fq = f"{app}.{ns}.svc.cluster.local"
    q = rng.choice(("same_ns", "other_ns", "outside"))
    if q == "same_ns":
        ask = f"Как обратиться к сервису из другого пода в namespace {ns}?"
        correct = f"http://{app}:{port}"
        wrong = [f"http://{app}:{target}", f"http://{app}:{node}", f"http://localhost:{port}"]
    elif q == "other_ns":
        other = rng.choice(("default", "monitoring", "staging"))
        ask = f"Как обратиться к сервису из пода в namespace {other}?"
        correct = f"http://{fq}:{port}"
        wrong = [f"http://{fq}:{target}", f"http://{app}:{port}", f"http://{fq}:{node}"]
    else:
        ask = "Как обратиться к сервису снаружи кластера (без Ingress и балансировщика)?"
        correct = f"http://<IP любой ноды>:{node}"
        wrong = [
            f"http://<IP любой ноды>:{port}",
            f"http://<IP любой ноды>:{target}",
            f"http://{fq}:{port}",
        ]
    return make_single_choice(
        rng,
        f"Приложение в контейнере слушает порт {target}. {ask}",
        correct,
        wrong,
        code=code,
        extra={"language": "yaml"},
        explanation=f"port {port} — порт сервиса, targetPort {target} — контейнера, "
        f"nodePort {node} — на нодах.",
    )


SERVICE_PORT = ItemTemplate(
    id="devops.k8s_service_port",
    specialization="devops",
    topic="kubernetes",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_service_port,
    a=1.3,
    b=0.2,
    title="Как достучаться до Service",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- ресурсы


def cpu_m(q: str) -> int:
    return int(q[:-1]) if q.endswith("m") else int(float(q) * 1000)


def mem_mi(q: str) -> int:
    return int(q[:-2]) * 1024 if q.endswith("Gi") else int(q[:-2])


def _gen_resources(rng: random.Random) -> Variant:
    while True:
        alloc_cpu = rng.choice(("3920m", "4", "7910m", "8", "2"))
        alloc_mem = rng.choice(("7Gi", "15Gi", "14848Mi", "31Gi", "3Gi"))
        used_cpu = rng.choice(("350m", "850m", "1200m", "600m"))
        used_mem = rng.choice(("512Mi", "1536Mi", "2Gi", "1Gi"))
        req_cpu = rng.choice(("100m", "250m", "500m", "0.5", "1", "200m", "750m"))
        req_mem = rng.choice(("128Mi", "256Mi", "512Mi", "1Gi", "768Mi", "2Gi"))
        lim_cpu = rng.choice(("1", "2", "1500m"))
        lim_mem = f"{mem_mi(req_mem) * 2}Mi"
        free_cpu = cpu_m(alloc_cpu) - cpu_m(used_cpu)
        free_mem = mem_mi(alloc_mem) - mem_mi(used_mem)
        if free_cpu <= 0 or free_mem <= 0 or cpu_m(lim_cpu) < cpu_m(req_cpu):
            continue
        by_cpu, by_mem = free_cpu // cpu_m(req_cpu), free_mem // mem_mi(req_mem)
        value = min(by_cpu, by_mem)
        if 1 <= value <= 40 and by_cpu != by_mem:
            break
    app = rng.choice(_APPS)
    code = "\n".join(
        [
            "# kubectl describe node worker-1",
            "Allocatable:",
            f"  cpu:     {alloc_cpu}",
            f"  memory:  {alloc_mem}",
            "Allocated resources (requests уже запущенных подов):",
            f"  cpu:     {used_cpu}",
            f"  memory:  {used_mem}",
            "",
            f"# контейнер Deployment {app}",
            "resources:",
            "  requests:",
            f'    cpu: "{req_cpu}"',
            f'    memory: "{req_mem}"',
            "  limits:",
            f'    cpu: "{lim_cpu}"',
            f'    memory: "{lim_mem}"',
        ]
    )
    return Variant(
        prompt=(
            f"В кластере одна рабочая нода worker-1. Сколько реплик {app} (по одному контейнеру "
            "в поде) планировщик сможет на ней разместить? Остальные поды не меняются."
        ),
        key=NumericKey(value, 0),
        code=code,
        extra={"answer_type": "integer", "language": "yaml"},
        explanation=f"По CPU {by_cpu}, по памяти {by_mem}: решают requests, ответ {value}.",
    )


RESOURCES = ItemTemplate(
    id="devops.k8s_resources",
    specialization="devops",
    topic="kubernetes",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_resources,
    a=1.4,
    b=0.5,
    title="Сколько подов поместится на ноду",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- ошибка в манифесте

MANIFEST_SYMPTOMS = {
    "deploy_selector": "kubectl apply отклоняет Deployment: «selector does not match template "
    "labels».",
    "probe": "Поды в статусе Running, но 0/1 READY; в событиях — «Readiness probe failed: "
    "connection refused». Приложение работает.",
    "limits": "kubectl apply отклоняет Deployment: requests памяти «must be less than or equal "
    "to memory limit».",
    "svc_selector": "Поды Ready, но kubectl get endpoints для сервиса показывает <none>.",
    "target": "Поды Ready, у сервиса есть Endpoints, но запросы к нему получают "
    "«connection refused».",
}


def _gen_manifest(rng: random.Random) -> Variant:
    app = rng.choice(_APPS)
    bug = rng.choice(tuple(MANIFEST_SYMPTOMS))
    port = rng.choice((8080, 3000, 5000, 9000))
    wrong_port = rng.choice([p for p in (80, 8081, 8000, 3001) if p != port])
    req = rng.choice((256, 512, 1024))
    ns = rng.choice(("prod", "shop", "team-a")) if rng.random() < 0.5 else None
    ver = f"1.{rng.randint(0, 20)}.{rng.randint(0, 9)}"
    marks: dict[str, int] = {}
    lines = ["apiVersion: apps/v1", "kind: Deployment", "metadata:", f"  name: {app}"]
    if ns:
        lines.append(f"  namespace: {ns}")
    lines += ["spec:", f"  replicas: {rng.randint(2, 5)}", "  selector:", "    matchLabels:"]
    marks["deploy_selector"] = len(lines)
    lines.append(f"      app: {app}-v2" if bug == "deploy_selector" else f"      app: {app}")
    lines += [
        "  template:",
        "    metadata:",
        "      labels:",
        f"        app: {app}",
        "    spec:",
        "      containers:",
        f"        - name: {app}",
        f"          image: registry.local/{app}:{ver}",
        "          ports:",
        f"            - containerPort: {port}",
        "          readinessProbe:",
        "            httpGet:",
        "              path: /healthz",
    ]
    marks["probe"] = len(lines)
    lines.append(f"              port: {wrong_port if bug == 'probe' else port}")
    lines += [
        "          resources:",
        "            requests:",
        f'              memory: "{req}Mi"',
        "            limits:",
    ]
    marks["limits"] = len(lines)
    lim = req // 2 if bug == "limits" else req * 2
    lines.append(f'              memory: "{lim}Mi"')
    lines += ["---", "apiVersion: v1", "kind: Service", "metadata:", f"  name: {app}"]
    if ns:
        lines.append(f"  namespace: {ns}")
    lines += ["spec:", "  selector:"]
    marks["svc_selector"] = len(lines)
    typo = app[:-1] if len(app) > 4 else app + "s"
    lines.append(f"    app: {typo if bug == 'svc_selector' else app}")
    lines += ["  ports:", "    - port: 80"]
    marks["target"] = len(lines)
    lines.append(f"      targetPort: {wrong_port if bug == 'target' else port}")
    return Variant(
        prompt=f"{MANIFEST_SYMPTOMS[bug]} В какой строке манифеста ошибка? Укажите номер строки.",
        key=marks[bug] + 1,
        code="\n".join(lines),
        extra={"language": "yaml", "line_count": len(lines)},
        explanation=f"{bug}: строка {marks[bug] + 1} — {lines[marks[bug]].strip()}",
    )


MANIFEST_BUG = ItemTemplate(
    id="devops.k8s_manifest_bug",
    specialization="devops",
    topic="kubernetes",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_manifest,
    a=1.5,
    b=0.6,
    title="Ошибка в манифесте Kubernetes",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- rolling update


def scaled(value: str, replicas: int, round_up: bool) -> int:
    if value.endswith("%"):
        raw = int(value[:-1]) * replicas / 100
        return math.ceil(raw) if round_up else math.floor(raw)
    return int(value)


def _gen_rollout(rng: random.Random) -> Variant:
    while True:
        r = rng.randint(3, 20)
        surge = rng.choice(("25%", "30%", "50%", "1", "2", "0", "10%"))
        unav = rng.choice(("25%", "30%", "0", "1", "2", "10%", "50%"))
        s, u = scaled(surge, r, True), scaled(unav, r, False)
        if s == 0 and u == 0:
            continue  # Kubernetes такую стратегию не примет
        if surge.endswith("%") or unav.endswith("%"):
            break
    q = rng.choice(("max_pods", "min_available"))
    if q == "max_pods":
        value, ask = (
            r + s,
            "Какое наибольшее число подов Deployment может существовать одновременно?",
        )
    else:
        value = r - u
        ask = "Сколько подов минимум остаются доступными (Ready) во время обновления?"
    code = "\n".join(
        [
            "spec:",
            f"  replicas: {r}",
            "  strategy:",
            "    type: RollingUpdate",
            "    rollingUpdate:",
            f"      maxSurge: {surge if not surge.endswith('%') else repr(surge)}",
            f"      maxUnavailable: {unav if not unav.endswith('%') else repr(unav)}",
        ]
    ).replace("'", '"')
    return Variant(
        prompt=f"Deployment обновляется на новую версию образа (rolling update). {ask}",
        key=NumericKey(value, 0),
        code=code,
        extra={"answer_type": "integer", "language": "yaml"},
        explanation=f"maxSurge → {s} (вверх), maxUnavailable → {u} (вниз); ответ {value}.",
    )


ROLLOUT = ItemTemplate(
    id="devops.k8s_rollout",
    specialization="devops",
    topic="kubernetes",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_rollout,
    a=1.4,
    b=1.2,
    title="maxSurge и maxUnavailable",
    time_limit_s=180,
)

TEMPLATES = [PROBES, SERVICE_PORT, RESOURCES, MANIFEST_BUG, ROLLOUT]
