# Railway (ya da başka bir konteyner platformu) için tek imaj: Python backend +
# claude-agent-sdk'nin ihtiyaç duyduğu Node.js tabanlı `claude` CLI'ı bir arada.
# Aynı imaj, frontend/renderer'ı da (bkz. backend/main.py'deki StaticFiles
# mount) kendi üzerinden statik olarak sunuyor — tek servis, tek URL.
FROM python:3.12-slim

# Node.js 22 (claude-agent-sdk'nin alt süreç olarak çalıştırdığı `claude` CLI
# için gerekli) + CLI'ın Linux'ta ihtiyaç duyduğu birkaç sistem kütüphanesi.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates libgcc-s1 libstdc++6 ripgrep \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# faster-whisper "base" modelini build sırasında indirip imaja gömüyoruz —
# Railway'de her yeniden başlatmada internet'e bağımlı, yavaş bir soğuk
# başlangıç (ve gereksiz veri kullanımı) yaşanmasın diye.
ENV WHISPER_MODEL_SIZE=base
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"

COPY backend/ backend/
COPY frontend/renderer/ frontend/renderer/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Railway kendi $PORT değerini enjekte eder; yerelde yoksa 8000'e düşer.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
