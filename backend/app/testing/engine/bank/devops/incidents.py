"""DevOps — инциденты: причина по симптомам, порядок действий при инциденте."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering, make_single_choice

# --------------------------------------------------------------------------- причина по симптомам

_CAUSES = {
    "oom": "Контейнер превысил memory limit и был убит (OOM)",
    "deleted_open": "Удалённый файл всё ещё открыт процессом, место не освобождено",
    "requests": "Requests подов больше, чем свободно на нодах",
    "image": "Неверный тег образа или нет доступа к реестру",
    "throttling": "Троттлинг CPU из-за слишком низкого CPU limit",
    "nofile": "Исчерпан лимит открытых файлов процесса (ulimit nofile)",
    "readiness": "Новые поды не проходят readinessProbe",
    "inodes": "Закончились inode на файловой системе",
}


def _gen_triage(rng: random.Random) -> Variant:
    app = rng.choice(("orders", "billing", "gateway", "search"))
    mem = rng.choice((256, 512, 1024))
    cpu = rng.choice(("200m", "250m", "500m"))
    ver = f"v1.{rng.randint(2, 30)}.{rng.randint(0, 9)}"
    disk = rng.choice(("/", "/var", "/data"))
    scenarios = [
        (
            f"Под {app} постоянно перезапускается: Last State: Terminated, Reason: OOMKilled, "
            f"Exit Code: 137. В манифесте limits.memory: {mem}Mi.",
            "oom",
        ),
        (
            f"df -h показывает, что {disk} заполнен на 100%, а du -sh {disk}* в сумме даёт "
            f"около {rng.randint(30, 60)}%. Недавно вручную удалили большой лог работающего "
            "сервиса.",
            "deleted_open",
        ),
        (
            f"Новые поды {app} висят в Pending; в событиях: «0/{rng.randint(3, 9)} nodes are "
            "available: Insufficient cpu».",
            "requests",
        ),
        (
            f"После релиза {ver} поды {app} в статусе ImagePullBackOff; в событиях: «manifest "
            "unknown».",
            "image",
        ),
        (
            f"Задержки {app} выросли в {rng.randint(5, 9)} раз, средняя загрузка CPU ноды "
            f"{rng.randint(20, 40)}%, а метрика container_cpu_cfs_throttled_periods_total растёт; "
            f"limits.cpu: {cpu}.",
            "throttling",
        ),
        (
            f"Сервис {app} под нагрузкой пишет в лог «accept: Too many open files», "
            "при этом CPU и память в норме.",
            "nofile",
        ),
        (
            f"Сразу после выкладки {ver} Ingress отдаёт 503 для {app}: новые поды Running, "
            "но 0/1 READY, старые уже удалены.",
            "readiness",
        ),
        (
            f"Запись файлов в {disk} падает с «No space left on device», хотя df -h показывает "
            f"{rng.randint(40, 70)}% занятого места; сервис создаёт миллионы мелких файлов "
            "кэша.",
            "inodes",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"Инцидент: {text}\nКакая причина наиболее вероятна?",
        _CAUSES[correct],
        [v for k, v in _CAUSES.items() if k != correct],
        explanation=f"Верно: {_CAUSES[correct]}",
    )


TRIAGE = ItemTemplate(
    id="devops.incident_triage",
    specialization="devops",
    topic="incidents",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_triage,
    a=1.3,
    b=1.0,
    title="Причина инцидента по симптомам",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- порядок действий


def _gen_response(rng: random.Random) -> Variant:
    app = rng.choice(("оплаты", "корзины", "авторизации", "поиска"))
    ver = f"v2.{rng.randint(0, 30)}.{rng.randint(0, 9)}"
    err = rng.choice((12, 25, 40, 60))
    days = rng.choice((2, 3, 5))
    steps = [
        f"Принять алерт «ошибки {app} {err}%» и назначить ответственного за инцидент",
        "Оценить влияние на пользователей, присвоить уровень серьёзности и открыть канал инцидента",
        f"Смягчить последствия: откатить релиз {ver}, вышедший перед ростом ошибок",
        "Убедиться по метрикам, что доля ошибок вернулась к норме",
        "Сообщить заинтересованным сторонам о восстановлении и закрыть инцидент",
        f"Провести безобвинительный разбор (postmortem) в течение {days} дней",
        "Завести задачи по итогам разбора и отслеживать их выполнение",
    ]
    return make_ordering(
        rng,
        f"Ночью резко выросла доля ошибок сервиса {app}. Расставьте действия дежурного "
        "и команды в правильном порядке.",
        steps,
        explanation=" → ".join(steps),
    )


RESPONSE = ItemTemplate(
    id="devops.incident_response_order",
    specialization="devops",
    topic="incidents",
    target_grade="senior",
    format=ItemFormat.ORDERING,
    generator=_gen_response,
    a=1.1,
    b=0.9,
    title="Порядок действий при инциденте",
    time_limit_s=150,
)

TEMPLATES = [TRIAGE, RESPONSE]
