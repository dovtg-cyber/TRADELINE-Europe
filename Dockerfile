FROM python:3.12-slim
WORKDIR /app
COPY server.py .
ENV PORT=10000 DB_PATH=/data/usage.db
RUN mkdir -p /data
EXPOSE 10000
CMD ["python", "server.py"]
