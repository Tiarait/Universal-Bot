FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /root/.cache

COPY . .

CMD ["python", "main.py"]
