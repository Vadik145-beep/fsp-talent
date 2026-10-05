"""DevOps — инфраструктура как код: состояние Terraform, итог terraform plan."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice

# --------------------------------------------------------------------------- состояние Terraform


def _gen_state(rng: random.Random) -> Variant:
    backend = rng.choice(
        (
            "S3 с таблицей блокировок DynamoDB",
            "Yandex Object Storage с блокировкой в YDB",
            "GCS",
            "Terraform Cloud",
            "PostgreSQL (backend pg)",
        )
    )
    cloud = rng.choice(("AWS", "Yandex Cloud", "GCP"))
    res = rng.choice(("security group", "бакет", "виртуальная машина", "подсеть"))
    true_pool = [
        f"Состояние хранят в удалённом бэкенде ({backend}) с блокировкой, чтобы два apply "
        "не шли одновременно",
        "terraform plan сравнивает конфигурацию, состояние и реальные ресурсы и показывает дрейф",
        "В файле состояния могут оказаться секреты, поэтому его не коммитят в git",
        f"Ресурс ({res}), созданный вручную, можно взять под управление через terraform import "
        "(или блок import)",
    ]
    false_pool = [
        "terraform.tfstate нужно коммитить в git, чтобы команда видела изменения",
        f"Если вручную изменить ресурс ({res}) в консоли {cloud}, Terraform запомнит это "
        "и не будет откатывать при следующем apply",
        "terraform destroy удаляет только файл состояния, а облачные ресурсы остаются",
        "Блокировка состояния нужна только для terraform destroy",
        "Если удалить файл состояния, Terraform сам найдёт свои ресурсы в облаке по именам",
    ]
    correct = rng.sample(true_pool, rng.randint(2, 3))
    wrong = rng.sample(false_pool, rng.randint(2, 3))
    return make_multi_choice(
        rng,
        f"Команда управляет инфраструктурой в {cloud} через Terraform. Отметьте все верные "
        "утверждения о состоянии (state).",
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation="Верные: " + "; ".join(correct),
    )


TF_STATE = ItemTemplate(
    id="devops.terraform_state",
    specialization="devops",
    topic="iac",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_state,
    a=1.1,
    b=-0.4,
    title="Состояние Terraform",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- итог terraform plan

# ресурс: (тип, имя, изменяемый атрибут, атрибут с пересозданием)
_RESOURCES = (
    (
        "aws_instance",
        "web",
        ("instance_type", ('"t3.small"', '"t3.medium"', '"t3.large"')),
        ("ami", ('"ami-0a1b2c3d"', '"ami-0f9e8d7c"', '"ami-05aa11bb"')),
    ),
    (
        "aws_s3_bucket",
        "logs",
        ("tags", ('{ env = "prod" }', '{ env = "stage" }')),
        ("bucket", ('"acme-logs-1"', '"acme-logs-2"', '"acme-logs-eu"')),
    ),
    (
        "aws_subnet",
        "private",
        ("tags", ('{ tier = "db" }', '{ tier = "app" }')),
        ("cidr_block", ('"10.0.1.0/24"', '"10.0.2.0/24"', '"10.0.3.0/24"')),
    ),
    (
        "aws_db_instance",
        "main",
        ("allocated_storage", ("20", "50", "100")),
        ("engine", ('"postgres"', '"mysql"')),
    ),
)


def plan_counts(changes: list[tuple[str, int, int]]) -> tuple[int, int, int]:
    """changes: (действие, было экземпляров, станет экземпляров) → (add, change, destroy)."""
    add = change = destroy = 0
    for action, old, new in changes:
        if action == "remove":
            destroy += old
        elif action == "new":
            add += new
        elif action == "update":
            change += min(old, new)
        elif action == "replace":
            add += min(old, new)
            destroy += min(old, new)
        add += max(0, new - old) if action in ("update", "replace", "keep") else 0
        destroy += max(0, old - new) if action in ("update", "replace", "keep") else 0
    return add, change, destroy


def _render(rtype: str, name: str, count: int, attrs: list[tuple[str, str]]) -> list[str]:
    lines = [f'resource "{rtype}" "{name}" {{']
    if count != 1:
        lines.append(f"  count = {count}")
    lines += [f"  {k} = {v}" for k, v in attrs]
    lines.append("}")
    return lines


def _gen_plan(rng: random.Random) -> Variant:
    chosen = rng.sample(_RESOURCES, 3)
    old_lines: list[str] = []
    new_lines: list[str] = []
    changes: list[tuple[str, int, int]] = []
    for rtype, name, (mut, mut_vals), (fn, fn_vals) in chosen:
        action = rng.choice(("keep", "update", "replace", "remove", "update", "replace"))
        old_count = rng.choice((1, 1, 2, 3)) if rtype == "aws_instance" else 1
        new_count = old_count
        if rtype == "aws_instance" and action != "remove" and rng.random() < 0.5:
            new_count = max(1, old_count + rng.choice((-1, 1, 2)))
        m1, m2 = rng.sample(mut_vals, 2)
        f1, f2 = rng.sample(fn_vals, 2)
        old_attrs = [(fn, f1), (mut, m1)]
        new_attrs = [
            (fn, f2 if action == "replace" else f1),
            (mut, m2 if action == "update" else m1),
        ]
        old_lines += [*_render(rtype, name, old_count, old_attrs), ""]
        if action != "remove":
            new_lines += [*_render(rtype, name, new_count, new_attrs), ""]
        changes.append((action, old_count, new_count))
    if rng.random() < 0.5:
        new_lines += [*_render("aws_eip", "nat", 1, [("domain", '"vpc"')]), ""]
        changes.append(("new", 0, 1))
    add, change, destroy = plan_counts(changes)
    if add + change + destroy == 0:
        return _gen_plan(rng)  # «No changes» — не наш случай, берём другой вариант
    code = (
        "# Применено ранее (совпадает с состоянием):\n"
        + "\n".join(old_lines).rstrip()
        + "\n\n# Новая версия конфигурации:\n"
        + "\n".join(new_lines).rstrip()
    )
    return Variant(
        prompt=(
            "Конфигурацию заменили на новую версию и запустили terraform plan. Дрейфа нет. "
            "Изменение ami, bucket, cidr_block и engine требует пересоздания ресурса, остальные "
            "атрибуты меняются на месте. Terraform выведет строку «Plan: X to add, Y to change, "
            "Z to destroy.» Запишите три числа X Y Z через пробел."
        ),
        key=f"{add} {change} {destroy}",
        code=code,
        extra={"language": "hcl"},
        explanation=f"Plan: {add} to add, {change} to change, {destroy} to destroy.",
    )


TF_PLAN = ItemTemplate(
    id="devops.terraform_plan",
    specialization="devops",
    topic="iac",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_plan,
    a=1.4,
    b=1.1,
    title="Итог terraform plan",
    time_limit_s=240,
)

TEMPLATES = [TF_STATE, TF_PLAN]
