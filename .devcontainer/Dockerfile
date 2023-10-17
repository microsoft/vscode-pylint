FROM mcr.microsoft.com/devcontainers/python:3.8

RUN python -m pip install --upgrade pip

COPY dev-requirements.txt ./
RUN python -m pip install -r dev-requirements.txt \
    && rm dev-requirements.txt

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt \
    && rm requirements.txt

COPY src/test/python_tests/requirements.txt .
RUN python -m pip install -r requirements.txt \
    && rm requirements.txt
