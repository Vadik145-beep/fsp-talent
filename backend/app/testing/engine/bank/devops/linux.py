"""DevOps — Linux: права доступа, команды администратора, сигналы."""

from __future__ import annotations

import random

from ...templates import (
    ItemFormat,
    ItemTemplate,
    Variant,
    make_multi_choice,
    make_single_choice,
)

# --------------------------------------------------------------------------- chmod


def symbolic(mode: int) -> str:
    out = []
    for shift in (6, 3, 0):
        d = (mode >> shift) & 7
        out.append(("r" if d & 4 else "-") + ("w" if d & 2 else "-") + ("x" if d & 1 else "-"))
    return "".join(out)


def _clause(who: str, digit: int) -> str:
    perms = ("r" if digit & 4 else "") + ("w" if digit & 2 else "") + ("x" if digit & 1 else "")
    return f"{who}={perms}"


def _gen_chmod(rng: random.Random) -> Variant:
    owner = rng.choice((4, 5, 6, 7, 7))
    group = rng.choice((0, 4, 5, 6, 7))
    other = rng.choice((0, 0, 4, 5, 1))
    mode = owner * 64 + group * 8 + other
    octal = f"{owner}{group}{other}"
    file_ = rng.choice(("deploy.sh", "app.conf", "id_rsa", "backup.tar", "run.py", "/srv/data"))
    q = rng.choice(("to_octal", "to_symbolic", "from_clauses"))
    if q == "to_octal":
        prompt = (
            f"ls -l показывает у файла {file_} права -{symbolic(mode)}. Какой командой "
            "chmod их выставить? Укажите права в восьмеричной записи из трёх цифр."
        )
        key: tuple[str, ...] = (octal, "0" + octal)
    elif q == "to_symbolic":
        prompt = (
            f"Выполнили chmod {octal} {file_}. Что покажет ls -l в поле прав после типа файла? "
            "Ответ — 9 символов, например rw-r--r--."
        )
        key = (symbolic(mode),)
    else:
        clauses = ",".join(_clause(w, d) for w, d in zip("ugo", (owner, group, other), strict=True))
        prompt = (
            f"Выполнили chmod {clauses} {file_}. Какие права получились в восьмеричной записи "
            "из трёх цифр?"
        )
        key = (octal, "0" + octal)
    return Variant(
        prompt=prompt,
        key=key,
        extra={"answer_type": "text", "max_length": 12},
        explanation=f"{octal} = {symbolic(mode)}",
    )


CHMOD = ItemTemplate(
    id="devops.chmod_octal",
    specialization="devops",
    topic="linux",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_chmod,
    a=1.2,
    b=-1.3,
    title="Права доступа: восьмеричная и символьная запись",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- команды


def _commands(rng: random.Random) -> list[tuple[str, str]]:
    port = rng.choice((80, 443, 5432, 6379, 8080, 9090))
    svc = rng.choice(("nginx", "postgresql", "docker", "app-api"))
    size = rng.choice((100, 200, 500))
    path = rng.choice(("/var/log", "/srv", "/opt/app", "/home"))
    word = rng.choice(("ERROR", "timeout", "OutOfMemory", "denied"))
    user = rng.choice(("deploy", "www-data", "app"))
    return [
        (
            f"Найти в {path} файлы *.log больше {size} МБ",
            f'find {path} -name "*.log" -size +{size}M',
        ),
        (f"Узнать, какой процесс слушает TCP-порт {port}", f"ss -tlnp | grep :{port}"),
        (f"Смотреть лог systemd-сервиса {svc} в реальном времени", f"journalctl -u {svc} -f"),
        ("Посмотреть свободное место на всех файловых системах", "df -h"),
        (f"Узнать, сколько места занимает каталог {path} целиком", f"du -sh {path}"),
        ("Показать процессы, отсортированные по потреблению памяти", "ps aux --sort=-%mem | head"),
        (
            f"Найти строку «{word}» во всех файлах каталога {path} рекурсивно",
            f'grep -rn "{word}" {path}',
        ),
        (
            f"Сделать пользователя {user} владельцем каталога {path} со всем содержимым",
            f"chown -R {user}:{user} {path}",
        ),
    ]


def _gen_commands(rng: random.Random) -> Variant:
    pool = _commands(rng)
    task, correct = rng.choice(pool)
    return make_single_choice(
        rng,
        f"Задача на сервере Linux: {task}. Какая команда это делает?",
        correct,
        [c for _, c in pool if c != correct],
        explanation=f"Верно: {correct}",
    )


LINUX_COMMANDS = ItemTemplate(
    id="devops.linux_commands",
    specialization="devops",
    topic="linux",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_commands,
    a=1.0,
    b=-1.6,
    title="Команда под задачу",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- кто имеет доступ


def can_access(mode: int, op: str, user: str, owner: str, group_members: set[str]) -> bool:
    bit = {"r": 4, "w": 2, "x": 1}[op]
    if user == "root":
        return op != "x" or bool(mode & 0o111)
    if user == owner:
        return bool((mode >> 6) & bit)  # для владельца — только его тройка
    if user in group_members:
        return bool((mode >> 3) & bit)
    return bool(mode & bit)


def _gen_file_access(rng: random.Random) -> Variant:
    owner, member, outsider = rng.sample(("alice", "bob", "carol", "dmitry", "elena", "fedor"), 3)
    group = rng.choice(("dev", "ops", "www", "backup"))
    op = rng.choice(("r", "w", "x"))
    op_text = {"r": "прочитать файл", "w": "записать в файл", "x": "запустить файл"}[op]
    while True:
        digits = [rng.randint(0, 7) for _ in range(3)]
        mode = digits[0] * 64 + digits[1] * 8 + digits[2]
        users = [owner, member, outsider, "root"]
        allowed = [u for u in users if can_access(mode, op, u, owner, {member})]
        if allowed and len(allowed) < 4:
            break
    labels = {
        owner: f"{owner} (владелец файла)",
        member: f"{member} (состоит в группе {group})",
        outsider: f"{outsider} (не владелец и не в группе {group})",
        "root": "root",
    }
    return make_multi_choice(
        rng,
        f"ls -l: -{symbolic(mode)} 1 {owner} {group} 4096 report.sh\n"
        f"Кто из пользователей сможет {op_text}? Отметьте всех. Других ограничений (ACL, "
        "SELinux, права каталога) нет.",
        [labels[u] for u in users if u in allowed],
        [labels[u] for u in users if u not in allowed],
        extra={"min_choices": 1},
        explanation=f"Права {mode:o}: доступ у {', '.join(allowed)}",
    )


FILE_ACCESS = ItemTemplate(
    id="devops.file_access",
    specialization="devops",
    topic="linux",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_file_access,
    a=1.3,
    b=-0.4,
    title="Кто может читать, писать, запускать",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- сигналы

_SIGNALS = {
    "HUP": "SIGHUP (1)",
    "INT": "SIGINT (2)",
    "KILL": "SIGKILL (9)",
    "TERM": "SIGTERM (15)",
    "STOP": "SIGSTOP (19)",
    "TSTP": "SIGTSTP (20)",
}
SIGNAL_NUMBERS = {"HUP": 1, "INT": 2, "KILL": 9, "TERM": 15}


def _gen_signals(rng: random.Random) -> Variant:
    proc = rng.choice(("nginx", "gunicorn", "node server.js", "java -jar app.jar", "postgres"))
    pid = rng.randint(1200, 65000)
    sig_for_code = rng.choice(tuple(SIGNAL_NUMBERS))
    code = 128 + SIGNAL_NUMBERS[sig_for_code]
    timeout = rng.choice((10, 20, 30))
    scenarios = [
        (
            f"Администратор выполнил kill {pid} для процесса {proc} без указания сигнала. "
            "Какой сигнал получит процесс?",
            "TERM",
        ),
        (
            f"Процесс {proc} (PID {pid}) завис и не реагирует на обычную остановку. Какой сигнал "
            "нельзя перехватить или проигнорировать, поэтому он гарантированно завершит процесс?",
            "KILL",
        ),
        (
            f"Пользователь нажал Ctrl+C в терминале, где запущен {proc}. Какой сигнал получит "
            "процесс?",
            "INT",
        ),
        (
            f"Пользователь нажал Ctrl+Z в терминале, где запущен {proc}. Какой сигнал получит "
            "процесс?",
            "TSTP",
        ),
        (
            f"Нужно, чтобы демон {proc} перечитал конфигурацию без остановки (классическое "
            "соглашение для демонов). Какой сигнал ему обычно отправляют?",
            "HUP",
        ),
        (
            f"Процесс {proc} в контейнере завершился с кодом выхода {code}. Каким сигналом его, "
            "скорее всего, остановили?",
            sig_for_code,
        ),
        (
            f"docker stop отправляет главному процессу контейнера сигнал, ждёт {timeout} с "
            "и только "
            "потом убивает принудительно. Какой сигнал отправляется первым?",
            "TERM",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        text,
        _SIGNALS[correct],
        [v for k, v in _SIGNALS.items() if k != correct],
        explanation=f"Верно: {_SIGNALS[correct]}",
    )


SIGNALS = ItemTemplate(
    id="devops.signals",
    specialization="devops",
    topic="linux",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_signals,
    a=1.2,
    b=-0.6,
    title="Сигналы процессов",
    time_limit_s=90,
)

TEMPLATES = [CHMOD, LINUX_COMMANDS, FILE_ACCESS, SIGNALS]
