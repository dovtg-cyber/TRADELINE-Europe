FROM python:3.12-slim
WORKDIR /app
COPY server.py ./server.py
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=10000
ENV DB_PATH=/tmp/tradeline.db
EXPOSE 10000
CMD ["python","server.py"]
