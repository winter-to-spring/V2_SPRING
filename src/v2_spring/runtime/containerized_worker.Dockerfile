FROM python:3.12-slim

WORKDIR /opt/v2

RUN mkdir -p /workspace /output

COPY isolated_worker_entry.py /opt/v2/isolated_worker_entry.py

CMD ["python", "/opt/v2/isolated_worker_entry.py", "--workspace", "/workspace"]
