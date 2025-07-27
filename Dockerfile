FROM docker.io/library/python:3.13.5-bookworm

WORKDIR /app

COPY main.py .

RUN python3 -m pip install requests
RUN python3 -m pip install cloudflare
RUN python3 -m pip install ruamel.yaml

ENTRYPOINT ["python3", "/app/main.py"]