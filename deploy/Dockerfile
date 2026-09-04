FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir gunicorn==23.0.0
COPY . /app
RUN useradd --uid 10001 --create-home hh520 && mkdir -p /state && chown hh520:hh520 /state
USER hh520
ENV HH520_DATABASE=/state/tasks.sqlite3
CMD ["gunicorn", "--bind", "0.0.0.0:8765", "--workers", "1", "--threads", "2", "--timeout", "20", "task_manager.wsgi:application"]
