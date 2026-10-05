"""Движок тестирования fsp-talent: чистая библиотека без БД и веба.

Публичный API для бэкенда:
- шаблоны: `ItemTemplate`, `TemplateRegistry`, `ItemInstance`, `PublicItem`, `check`,
  `example_registry()` / `EXAMPLE_TEMPLATES`;
- адаптивный тест: `ItemBank`, `BankItem`, `CATConfig`, `CATSession`, `SessionState`, `CATResult`;
- грейд: `decide`, `GradeThresholds`, `can_attempt`, `Attempt`, `Eligibility`;
- утечки: `detect_leaks`, `ItemObservation`, `candidate_anomalies`, `CandidateResponse`;
- калибровка: `calibrate_item`, `activation_check`;
- IRT: `estimate_theta`, `prob`, `information`.
Подробно — docs/testing/engine.md.
"""

from .bank_examples import EXAMPLE_TEMPLATES, example_registry
from .calibration import (
    ActivationRule,
    CalibrationResult,
    activation_check,
    calibrate_bank,
    calibrate_item,
)
from .cat import (
    AnswerRecord,
    BankItem,
    CATConfig,
    CATResult,
    CATSession,
    ItemBank,
    SessionFinishedError,
    SessionState,
    TopicStat,
)
from .constants import GRADE_LABELS, GRADES, SPECIALIZATIONS
from .grading import (
    DEFAULT_THRESHOLDS,
    FAILED_RETRY_COOLDOWN_DAYS,
    GRADE_CHANGE_COOLDOWN_DAYS,
    Attempt,
    Eligibility,
    GradeDecision,
    GradeThresholds,
    can_attempt,
    decide,
    grade_for_theta,
    is_grade_change,
    next_grade_change_date,
)
from .irt import (
    ThetaEstimate,
    estimate_theta,
    estimate_theta_for_grade,
    information,
    leave_one_out_thetas,
    person_fit_lz,
    prior_for_grade,
    prob,
)
from .leak import (
    CandidateAnomalyConfig,
    CandidateAnomalyReport,
    CandidateResponse,
    ItemLeakReport,
    ItemObservation,
    LeakConfig,
    candidate_anomalies,
    detect_leaks,
    flagged_item_ids,
)
from .templates import (
    ItemFormat,
    ItemInstance,
    ItemTemplate,
    NumericKey,
    PublicItem,
    TemplateRegistry,
    TemplateStatus,
    Variant,
    check,
    correct_response,
)

__all__ = [
    "DEFAULT_THRESHOLDS",
    "EXAMPLE_TEMPLATES",
    "FAILED_RETRY_COOLDOWN_DAYS",
    "GRADES",
    "GRADE_CHANGE_COOLDOWN_DAYS",
    "GRADE_LABELS",
    "SPECIALIZATIONS",
    "ActivationRule",
    "AnswerRecord",
    "Attempt",
    "BankItem",
    "CATConfig",
    "CATResult",
    "CATSession",
    "CalibrationResult",
    "CandidateAnomalyConfig",
    "CandidateAnomalyReport",
    "CandidateResponse",
    "Eligibility",
    "GradeDecision",
    "GradeThresholds",
    "ItemBank",
    "ItemFormat",
    "ItemInstance",
    "ItemLeakReport",
    "ItemObservation",
    "ItemTemplate",
    "LeakConfig",
    "NumericKey",
    "PublicItem",
    "SessionFinishedError",
    "SessionState",
    "TemplateRegistry",
    "TemplateStatus",
    "ThetaEstimate",
    "TopicStat",
    "Variant",
    "activation_check",
    "calibrate_bank",
    "calibrate_item",
    "can_attempt",
    "candidate_anomalies",
    "check",
    "correct_response",
    "decide",
    "detect_leaks",
    "estimate_theta",
    "estimate_theta_for_grade",
    "example_registry",
    "flagged_item_ids",
    "grade_for_theta",
    "information",
    "is_grade_change",
    "leave_one_out_thetas",
    "next_grade_change_date",
    "person_fit_lz",
    "prior_for_grade",
    "prob",
]
