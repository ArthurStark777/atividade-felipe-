FROM python:3.15-slim

# Não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 helpdesk && mkdir /dados && chown helpdesk /dados

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

USER helpdesk
# Banco próprio deste serviço (um arquivo SQLite no volume /dados).
# FORWARDED_ALLOW_IPS: o gateway manda o IP real de quem fez login em X-Forwarded-For,
# e o limite de tentativas de login usa esse IP. Só o gateway alcança este serviço.
ENV DATABASE_URL=sqlite:////dados/usuarios.db \
    FORWARDED_ALLOW_IPS=* \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
