# Образ для сборки документации: pandoc (Markdown → DOCX), LibreOffice Writer + python3-uno
# (обновление оглавления, встраивание шрифтов, экспорт PDF), poppler (PDF → PNG для проверки),
# шрифты брендбука ФСП с кириллицей: Inter (текст), JetBrains Mono (заголовки, код), DejaVu (запас).
# Собирает build_docs.py:  docker build -t fsp-docs-render docs/solution/tools/docker
FROM debian:bookworm-slim
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       pandoc libreoffice-writer-nogui python3-uno poppler-utils fontconfig \
       fonts-dejavu fonts-inter fonts-jetbrains-mono \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f
WORKDIR /work
