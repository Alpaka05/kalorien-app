FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY static ./static

RUN mkdir -p /app/data

EXPOSE 5000

# Ein Worker mit Threads: SQLite verträgt parallele Schreibzugriffe schlecht,
# und die Wartezeit steckt ohnehin in den API-Aufrufen, nicht in der CPU.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
