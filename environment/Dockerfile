FROM python:3.12-slim

WORKDIR /app

COPY sealflow /app/sealflow
COPY programs /app/programs

RUN mkdir -p /app/output /logs/verifier

CMD ["/bin/bash"]
