FROM python:3.13.7-slim as base

ENV FLASK_APP=main.py
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG UID=10001
RUN adduser \
	--disabled-password \
	--gecos "" \
	--home "/nonexistent" \
	--shell "/sbin/nologin" \
	--no-create-home \
	--uid "${UID}" \
	appuser

RUN --mount=type=cache,target=/root/.cache/pip \
	--mount=type=bind,source=requirements.txt,target=requirements.txt \
	python -m pip install -r requirements.txt

USER appuser

COPY . .

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
