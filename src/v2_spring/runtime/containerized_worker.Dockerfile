FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

WORKDIR /opt/v2

RUN mkdir -p /workspace /output

COPY isolated_worker_entry.py /opt/v2/isolated_worker_entry.py
COPY container_log_capture.py /opt/v2/container_log_capture.py

CMD ["python", "/opt/v2/isolated_worker_entry.py", "--workspace", "/workspace"]
