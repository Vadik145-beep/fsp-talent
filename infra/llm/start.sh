#!/bin/sh
# Контейнер llm: открытая модель Qwen2.5-1.5B-Instruct (Apache 2.0) в llama.cpp на этом же сервере.
# При первом запуске скачивает GGUF с Hugging Face в том /models и проверяет SHA-256,
# дальше запускается сразу. OpenAI-совместимый API: http://llm:8080/v1 (наружу порт не открыт).
set -eu

MODEL_URL="${LLM_MODEL_URL:-https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
MODEL_FILE="${LLM_MODEL_FILE:-qwen2.5-1.5b-instruct-q4_k_m.gguf}"
MODEL_SHA256="${LLM_MODEL_SHA256:-6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e}"
MODEL="/models/$MODEL_FILE"

if [ ! -f "$MODEL.ok" ]; then
  if [ ! -f "$MODEL" ]; then
    echo "llm: скачиваю модель $MODEL_URL"
    # -C - докачивает оборванную загрузку; HTTP/1.1 — на HTTP/2 CDN иногда рвёт поток
    n=0
    until curl -fL --http1.1 --retry 5 --retry-delay 10 --retry-all-errors \
      -C - -o "$MODEL.part" "$MODEL_URL"; do
      n=$((n + 1))
      if [ "$n" -ge 30 ]; then
        echo "llm: не удалось скачать модель — проверьте доступ к huggingface.co" >&2
        exit 1
      fi
      echo "llm: загрузка прервалась, продолжаю ($n)"
      sleep 10
    done
    mv "$MODEL.part" "$MODEL"
  fi
  echo "llm: проверяю SHA-256"
  if ! echo "$MODEL_SHA256  $MODEL" | sha256sum -c -; then
    echo "llm: контрольная сумма не совпала — удаляю файл, при перезапуске скачаю заново" >&2
    rm -f "$MODEL"
    exit 1
  fi
  touch "$MODEL.ok"
fi

# 2 ядра: два потока, один запрос за раз (-np 1), контекст 4096 токенов
exec /app/llama-server -m "$MODEL" \
  --host 0.0.0.0 --port 8080 \
  --alias "${LLM_ALIAS:-qwen2.5-1.5b-instruct}" \
  -c "${LLM_CTX:-4096}" --threads "${LLM_THREADS:-2}" -np 1 \
  --no-webui
