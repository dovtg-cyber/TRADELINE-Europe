FROM python:3.12-slim

WORKDIR /app

COPY server.py ./server.py

ENV PORT=10000
ENV DB_PATH=/tmp/tradeline.db

EXPOSE 10000

CMD ["python", "server.py"]
