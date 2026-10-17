FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt \
    && useradd --create-home --uid 10001 moviegraph
COPY --chown=moviegraph:moviegraph app ./app
COPY --chown=moviegraph:moviegraph scripts ./scripts
COPY --chown=moviegraph:moviegraph cypher ./cypher
RUN mkdir -p data artifacts && chown moviegraph:moviegraph data artifacts
USER moviegraph
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
