FROM python:3.12-slim
WORKDIR /app
COPY backend/ backend/
COPY data/sample/ data/sample/
RUN pip install --no-cache-dir -c backend/requirements.lock.txt -e ./backend
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic -c backend/alembic.ini upgrade head && exec python -m uvicorn ta_backend.main:app --host 0.0.0.0 --port 8000"]
