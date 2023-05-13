FROM python:3

WORKDIR /tg2

COPY main.py .
COPY config.py .
COPY requirements.txt .

RUN pip install --no-cache-dir pip && \
    pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]