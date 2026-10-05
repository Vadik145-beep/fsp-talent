"""Кабинет администратора — заглушки поверх фикстур (реальная логика — волны 2b, 3a, 4c, 5b)."""

import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.admin.repository import AdminRepository
from app.admin.schemas import (
    AdminUserUpdate,
    PlatformSettingsUpdate,
    ReportCreate,
    ReportUpdate,
    VacancyTestRequest,
)
from app.common.enums import (
    GradeCode,
    InvitationStatus,
    ItemStatus,
    ReportStatus,
    Role,
)
from app.common.fixtures import Record
from app.common.schemas import paginate
from app.core.errors import AppError, not_found

SUMMARY_DROP = ("preview_variants", "description")


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class AdminService:
    def __init__(self, repo: AdminRepository | None = None) -> None:
        self.repo = repo or AdminRepository()

    # ---------- дашборд ----------

    def dashboard(self) -> dict[str, Any]:
        users = Counter(u["role"] for u in self.repo.users())
        invitations = Counter(i["status"] for i in self.repo.invitations())
        sessions = [s for s in self.repo.test_sessions() if s["status"] == "finished"]
        by_day = Counter(s["finished_at"][:10] for s in sessions)
        total = sum(invitations.values())
        leaks = [
            {
                "item_id": it["id"],
                "title": it["title"],
                "specialization": it["specialization"],
                "leak_score": it["leak_score"],
            }
            for it in self.repo.items()
            if it["leak_flag"]
        ]
        return {
            "users_by_role": dict(users),
            "tests_total": len(sessions),
            "tests_by_day": [{"date": d, "count": n} for d, n in sorted(by_day.items())],
            "invitations_by_status": dict(invitations),
            "invite_to_accept_conversion": (
                round(invitations[InvitationStatus.accepted] / total, 2) if total else 0.0
            ),
            "leak_flags": leaks,
            "open_reports": sum(
                1
                for r in self.repo.reports()
                if r["status"] in (ReportStatus.new, ReportStatus.in_review)
            ),
        }

    # ---------- пользователи ----------

    def users(
        self, q: str | None, role: Role | None, blocked: bool | None, page: int, page_size: int
    ) -> dict[str, Any]:
        items = self.repo.users()
        if q:
            needle = q.lower()
            items = [
                u for u in items if needle in u["email"].lower() or needle in u["full_name"].lower()
            ]
        if role:
            items = [u for u in items if u["role"] == role]
        if blocked is not None:
            items = [u for u in items if u["blocked"] == blocked]
        return paginate(items, page, page_size)

    def update_user(self, user_id: int, body: AdminUserUpdate, actor_id: int) -> dict[str, Any]:
        user = self.repo.user(user_id)
        if user is None:
            raise not_found("user", user_id)
        if user_id == actor_id and (body.blocked or (body.role and body.role != Role.admin)):
            raise AppError(409, "cannot_change_self", "Нельзя заблокировать или понизить себя")
        data = dict(user)
        data.update(body.model_dump(exclude_none=True))
        return data

    def user_audit(self, user_id: int) -> list[Record]:
        if self.repo.user(user_id) is None:
            raise not_found("user", user_id)
        return [
            a
            for a in self.repo.audit()
            if a["actor_user_id"] == user_id
            or (a["target_type"] in ("user", "candidate") and a["target_id"] == user_id)
        ]

    # ---------- компании ----------

    def _company_view(self, company: Record) -> dict[str, Any]:
        invs = [i for i in self.repo.invitations() if i["company_id"] == company["id"]]
        answered = [
            i for i in invs if i["status"] in (InvitationStatus.accepted, InvitationStatus.declined)
        ]
        return {
            **company,
            "recruiters_count": sum(
                1 for r in self.repo.recruiters() if r["company_id"] == company["id"]
            ),
            "invitations_sent": len(invs),
            "response_rate": round(len(answered) / len(invs), 2) if invs else 0.0,
            "reports_count": sum(
                1 for r in self.repo.reports() if r["company_id"] == company["id"]
            ),
        }

    def companies(self) -> list[dict[str, Any]]:
        return [self._company_view(c) for c in self.repo.companies()]

    def update_company(self, company_id: int, blocked: bool) -> dict[str, Any]:
        company = self.repo.company(company_id)
        if company is None:
            raise not_found("company", company_id)
        view = self._company_view(company)
        view["blocked"] = blocked
        return view

    # ---------- настройки ----------

    def settings(self) -> Record:
        return self.repo.settings()

    def update_settings(self, body: PlatformSettingsUpdate) -> Record:
        data = self.repo.settings()
        data.update(body.model_dump(exclude_none=True))
        return data

    # ---------- банк задач ----------

    def items(
        self,
        specialization: str | None,
        topic: str | None,
        status: ItemStatus | None,
        leak_flag: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        items = self.repo.items()
        if specialization:
            items = [i for i in items if i["specialization"] == specialization]
        if topic:
            items = [i for i in items if i["topic"] == topic]
        if status:
            items = [i for i in items if i["status"] == status]
        if leak_flag is not None:
            items = [i for i in items if i["leak_flag"] == leak_flag]
        summaries = [{k: v for k, v in i.items() if k not in SUMMARY_DROP} for i in items]
        return paginate(summaries, page, page_size)

    def item(self, item_id: int) -> dict[str, Any]:
        item = self.repo.item(item_id)
        if item is None:
            raise not_found("item", item_id)
        return dict(item)

    def retire_item(self, item_id: int) -> dict[str, Any]:
        item = self.item(item_id)
        if item["status"] == ItemStatus.retired:
            raise AppError(409, "invalid_transition", "Шаблон уже выведен из оборота")
        item["status"] = ItemStatus.retired
        return item

    def approve_item(self, item_id: int) -> dict[str, Any]:
        item = self.item(item_id)
        if item["status"] != ItemStatus.draft:
            raise AppError(409, "invalid_transition", "Одобрить можно только черновик")
        item["status"] = ItemStatus.pilot
        return item

    def coverage(self) -> list[dict[str, Any]]:
        cells: dict[tuple[str, str], dict[str, Any]] = {}
        for topic in self.repo.topics():
            for grade in GradeCode:
                cells[(topic["id"], grade.value)] = {
                    "specialization": topic["specialization"],
                    "topic": topic["id"],
                    "topic_label": topic["label"],
                    "grade": grade.value,
                    "active": 0,
                    "pilot": 0,
                }
        for item in self.repo.items():
            cell = cells.get((item["topic"], item["target_grade"]))
            if cell and item["status"] in (ItemStatus.active, ItemStatus.pilot):
                cell[item["status"]] += 1
        return list(cells.values())

    def recalibrate(self) -> dict[str, Any]:
        active = [i for i in self.repo.items() if i["status"] == ItemStatus.active]
        changes = [
            {
                "item_id": i["id"],
                "a_before": i["a"],
                "a_after": round(i["a"] * 1.03, 2),
                "b_before": i["b"],
                "b_after": round(i["b"] + 0.05, 2),
            }
            for i in active[:5]
        ]
        return {
            "started_at": _now(),
            "items_recalibrated": len(active),
            "pilot_promoted": sum(1 for i in self.repo.items() if i["status"] == ItemStatus.pilot),
            "changes": changes,
        }

    # ---------- задания из вакансий ----------

    def vacancy_tests(self) -> list[Record]:
        return self.repo.vacancy_tests()

    def build_vacancy_test(self, body: VacancyTestRequest) -> dict[str, Any]:
        """Заглушка: выбираем пример, ближайший по словам. Настоящий разбор — волна 3c (T4.8)."""
        words = set(re.findall(r"[a-zа-яё0-9]+", body.text.lower()))
        examples = self.repo.vacancy_tests()
        if not examples:
            raise AppError(501, "not_implemented", "Будет реализовано в волне 3c")

        def overlap(example: Record) -> int:
            return len(words & set(re.findall(r"[a-zа-яё0-9]+", example["vacancy_text"].lower())))

        best_example: Record = max(examples, key=overlap)
        best = dict(best_example)
        best.update(vacancy_text=body.text, vacancy_title=body.text[:60])
        if body.specialization:
            best["specialization"] = body.specialization
        return best

    # ---------- жалобы и журнал ----------

    def reports(self, status: ReportStatus | None) -> list[Record]:
        items = self.repo.reports()
        if status:
            items = [r for r in items if r["status"] == status]
        return sorted(items, key=lambda r: r["created_at"], reverse=True)

    def update_report(self, report_id: int, body: ReportUpdate) -> dict[str, Any]:
        report = self.repo.report(report_id)
        if report is None:
            raise not_found("report", report_id)
        data = dict(report)
        data.update(status=body.status, resolution=body.resolution)
        if body.status in (ReportStatus.resolved, ReportStatus.rejected):
            data["resolved_at"] = _now()
        return data

    def create_report(self, body: ReportCreate, candidate_id: int) -> dict[str, Any]:
        company = self.repo.company(body.company_id)
        if company is None:
            raise not_found("company", body.company_id)
        return {
            **body.model_dump(),
            "id": max((r["id"] for r in self.repo.reports()), default=0) + 1,
            "company_name": company["name"],
            "reporter_candidate_id": candidate_id,
            "status": ReportStatus.new,
            "resolution": None,
            "created_at": _now(),
            "resolved_at": None,
        }

    def audit(
        self, action: str | None, target_type: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        items = sorted(self.repo.audit(), key=lambda a: a["at"], reverse=True)
        if action:
            items = [a for a in items if a["action"] == action]
        if target_type:
            items = [a for a in items if a["target_type"] == target_type]
        return paginate(items, page, page_size)
