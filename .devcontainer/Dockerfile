FROM mcr.microsoft.com/devcontainers/python:3

RUN python -m pip install --upgrade pip

COPY src/test/python_tests/requirements.txt .
RUN python -m pip install -r requirements.txt \
    && rm requirements.txt
