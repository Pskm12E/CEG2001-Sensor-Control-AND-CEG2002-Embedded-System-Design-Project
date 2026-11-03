FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Server Manager checks out sources with umask 077; assign them to the runtime user.
COPY --chown=1000:1000 server.py ./
COPY --chown=1000:1000 static ./static
USER 1000:1000
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=2).close()"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765", "--public-origin", "https://pest.4bytedigi.com"]
