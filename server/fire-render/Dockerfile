# fire-render – the situational scheme made on the server (see app.py). The plugin's scripts are not baked
# in: the entrypoint clones the public repository into the volume and app.py pulls it every 5 minutes.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN useradd --uid 10003 --create-home render && mkdir -p /data && chown render /data
COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint.sh
USER render
ENV REPO_DIR=/data/repo DATA_DIR=/data/sesii PORT=8080 MPLBACKEND=Agg PYTHONUNBUFFERED=1
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4)"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
