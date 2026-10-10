"""Тексты писем: подтверждение почты и сброс пароля. Ссылки ведут на фронтенд."""

from urllib.parse import urlencode

from app.core.config import get_settings
from app.core.email import layout_html, send_email_async


def frontend_link(path: str, token: str) -> str:
    base = get_settings().public_frontend_url.rstrip("/")
    return f"{base}{path}?{urlencode({'token': token})}"


async def send_verification_email(to: str, full_name: str, token: str) -> bool:
    hours = get_settings().email_verify_ttl_hours
    link = frontend_link("/verify-email", token)
    greeting = f"Здравствуйте, {full_name}!"
    lines = [
        "Вы зарегистрировались на платформе подбора IT-специалистов «ФСП · Таланты».",
        f"Подтвердите почту по ссылке — она действует {hours} ч.",
        "Если вы не регистрировались, просто проигнорируйте письмо.",
    ]
    text = "\n\n".join([greeting, *lines, link])
    return await send_email_async(
        to, "Подтвердите почту", text, layout_html([greeting, *lines], ("Подтвердить почту", link))
    )


async def send_password_reset_email(to: str, full_name: str, token: str) -> bool:
    minutes = get_settings().password_reset_ttl_min
    link = frontend_link("/reset-password", token)
    greeting = f"Здравствуйте, {full_name}!"
    lines = [
        "Мы получили запрос на сброс пароля.",
        f"Задайте новый пароль по ссылке — она действует {minutes} мин.",
        "Если вы не запрашивали сброс, проигнорируйте письмо: пароль не изменится.",
    ]
    text = "\n\n".join([greeting, *lines, link])
    return await send_email_async(
        to, "Сброс пароля", text, layout_html([greeting, *lines], ("Задать новый пароль", link))
    )
