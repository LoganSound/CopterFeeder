FROM python:3.10-slim

WORKDIR /usr/local/bin

COPY feed_copterspotter.py . 
COPY requirements.txt .
COPY .env . 

RUN pip install -r requirements.txt

CMD ["python3", "feed_copterspotter.py", "-w", "-v"]
