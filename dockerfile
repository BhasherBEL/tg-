FROM python:3

WORKDIR /tg2

COPY requirements.txt .

RUN pip install --no-cache-dir pip && \
    pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY config.py .

CMD ["python", "main.py"]
