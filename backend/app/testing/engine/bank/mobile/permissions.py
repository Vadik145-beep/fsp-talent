"""Mobile / публикация и разрешения: dangerous vs normal, runtime-разрешения, поля версий."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice, make_single_choice

# --------------------------------------------------------------------------- dangerous / normal

DANGEROUS = (
    "CAMERA",
    "RECORD_AUDIO",
    "ACCESS_FINE_LOCATION",
    "ACCESS_COARSE_LOCATION",
    "READ_CONTACTS",
    "POST_NOTIFICATIONS",
    "READ_MEDIA_IMAGES",
    "READ_CALENDAR",
    "SEND_SMS",
    "CALL_PHONE",
    "BODY_SENSORS",
    "READ_PHONE_STATE",
    "BLUETOOTH_CONNECT",
)
NORMAL = (
    "INTERNET",
    "ACCESS_NETWORK_STATE",
    "ACCESS_WIFI_STATE",
    "VIBRATE",
    "WAKE_LOCK",
    "RECEIVE_BOOT_COMPLETED",
    "FOREGROUND_SERVICE",
    "SET_WALLPAPER",
    "NFC",
    "USE_BIOMETRIC",
)


def _gen_dangerous(rng: random.Random) -> Variant:
    n_bad = rng.randint(2, 4)
    correct = [f"android.permission.{p}" for p in rng.sample(DANGEROUS, n_bad)]
    wrong = [f"android.permission.{p}" for p in rng.sample(NORMAL, 6 - n_bad)]
    app = rng.choice(("мессенджер", "фитнес-трекер", "доставку еды", "банк", "навигатор"))
    return make_multi_choice(
        rng,
        f"Вы делаете {app} под Android 13 (targetSdk 33). Все разрешения ниже объявлены "
        "в AndroidManifest.xml. Для каких из них приложение должно дополнительно запросить "
        "согласие пользователя во время работы (runtime-запрос)? Отметьте все такие.",
        correct,
        wrong,
        extra={"platform": "android"},
        explanation="Runtime-запрос нужен для dangerous-разрешений; normal выдаются при установке.",
    )


DANGEROUS_PERMISSIONS = ItemTemplate(
    id="mobile.android_dangerous_permissions",
    specialization="mobile",
    topic="publishing_permissions",
    target_grade="intern",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_dangerous,
    a=1.1,
    b=-1.6,
    title="Какие разрешения запрашивать в рантайме",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- runtime-разрешения

_OUT_DIALOG = "Покажется системный диалог запроса разрешения"
_OUT_DENIED = "Диалог не покажется, колбэк сразу получит false (отказ)"
_OUT_GRANTED = "Диалог не покажется, колбэк сразу получит true (разрешено)"
_OUT_CRASH = "Приложение упадёт с SecurityException"
_OUT_SETTINGS = "Система сама откроет экран настроек приложения"
_OUT_RATIONALE = "Система сама покажет пользователю объяснение (rationale) и затем диалог"

_PERMS = (
    ("CAMERA", "доступ к камере"),
    ("RECORD_AUDIO", "доступ к микрофону"),
    ("ACCESS_FINE_LOCATION", "доступ к точной геолокации"),
    ("READ_CONTACTS", "доступ к контактам"),
    ("POST_NOTIFICATIONS", "показ уведомлений"),
)


def _gen_runtime(rng: random.Random) -> Variant:
    perm, what = rng.choice(_PERMS)
    histories = [
        (
            "Приложение установлено только что и ещё ни разу не запрашивало это разрешение.",
            _OUT_DIALOG,
        ),
        ("Пользователь один раз нажал «Не разрешать» в системном диалоге.", _OUT_DIALOG),
        (
            "Пользователь уже дважды нажимал «Не разрешать» в системном диалоге (в разные дни).",
            _OUT_DENIED,
        ),
        ("Пользователь ранее нажал «Разрешить», и с тех пор ничего не менялось.", _OUT_GRANTED),
        (
            "Пользователь дважды нажал «Не разрешать», затем сам включил разрешение "
            "в настройках приложения.",
            _OUT_GRANTED,
        ),
        (
            "Пользователь дважды нажал «Не разрешать», затем удалил приложение и установил "
            "его заново.",
            _OUT_DIALOG,
        ),
    ]
    history, correct = rng.choice(histories)
    distractors = [
        o
        for o in (_OUT_DIALOG, _OUT_DENIED, _OUT_GRANTED, _OUT_CRASH, _OUT_SETTINGS, _OUT_RATIONALE)
        if o != correct
    ]
    return make_single_choice(
        rng,
        f"Android 13, targetSdk 33. Разрешение android.permission.{perm} ({what}) "
        f"объявлено в манифесте. {history} Теперь приложение вызывает "
        f"permissionLauncher.launch(Manifest.permission.{perm}) "
        "(ActivityResultContracts.RequestPermission). Что произойдёт?",
        correct,
        distractors,
        extra={"platform": "android"},
        explanation="С Android 11 после двух отказов система больше не показывает диалог; "
        "уже выданное разрешение возвращается сразу; переустановка сбрасывает состояние.",
    )


RUNTIME_PERMISSIONS = ItemTemplate(
    id="mobile.android_runtime_permission_flow",
    specialization="mobile",
    topic="publishing_permissions",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_runtime,
    a=1.3,
    b=-0.2,
    title="Повторный запрос runtime-разрешения",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- поля версий


def _gen_version_field(rng: random.Random) -> Variant:
    app = rng.choice(("Маркет", "Такси", "Заметки", "Фитнес", "Банк", "Погода", "Кино"))
    major, minor, patch = rng.randint(1, 5), rng.randint(0, 12), rng.randint(0, 9)
    name = f"{major}.{minor}.{patch}"
    code = major * 10000 + minor * 100 + patch
    build = rng.randint(10, 400)
    min_api = rng.choice((24, 26, 28))
    cases = [
        (
            f"Android-приложение «{app}»: в Google Play уже загружена сборка с versionName "
            f"«{name}» и versionCode {code}. Вы исправили опечатку и загружаете новую сборку, "
            f"но Play Console отвечает: «Version code {code} has already been used». "
            "Какое свойство в defaultConfig модуля нужно увеличить?",
            ("versionCode", "version code"),
        ),
        (
            f"Android-приложение «{app}» должно устанавливаться на устройства начиная с API "
            f"{min_api}. Какое свойство в defaultConfig модуля задаёт это ограничение?",
            ("minSdk", "minSdkVersion"),
        ),
        (
            f"Android-приложение «{app}»: Google Play каждый год повышает требование к версии "
            "API, под которую собрано и протестировано приложение (от неё зависит поведение "
            "системы, например новые ограничения фоновой работы). Какое свойство в defaultConfig "
            "нужно поднять?",
            ("targetSdk", "targetSdkVersion"),
        ),
        (
            f"Android-приложение «{app}»: пользователь должен видеть в Google Play версию "
            f"«{name}». Какое свойство в defaultConfig задаёт эту строку?",
            ("versionName", "version name"),
        ),
        (
            f"iOS-приложение «{app}» версии {name}: сборка {build} уже загружена в App Store "
            "Connect. Новая сборка с той же версией отклоняется с ошибкой о повторном номере "
            "сборки. Какой ключ Info.plist (поле Build в Xcode) нужно увеличить?",
            ("CFBundleVersion", "CURRENT_PROJECT_VERSION"),
        ),
        (
            f"iOS-приложение «{app}»: пользователь должен видеть в App Store версию «{name}». "
            "Какой ключ Info.plist (поле Version в Xcode) задаёт эту строку?",
            ("CFBundleShortVersionString", "MARKETING_VERSION"),
        ),
    ]
    prompt, answers = rng.choice(cases)
    return Variant(
        prompt=prompt + " Введите имя свойства или ключа.",
        key=answers,
        extra={"platform": "ios" if "iOS" in prompt else "android"},
        explanation="Допустимые ответы: " + ", ".join(answers),
    )


VERSION_FIELDS = ItemTemplate(
    id="mobile.release_version_fields",
    specialization="mobile",
    topic="publishing_permissions",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_version_field,
    a=0.9,
    b=-1.9,
    title="Поля версий при публикации",
    time_limit_s=120,
)

TEMPLATES = (DANGEROUS_PERMISSIONS, RUNTIME_PERMISSIONS, VERSION_FIELDS)
