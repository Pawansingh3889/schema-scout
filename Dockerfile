# Run schema-scout without a local Python setup.
#
#   docker build -t schema-scout .
#   docker run --rm schema-scout demo --large            # no DB needed
#
# To point it at a real SQL Server you also need Microsoft's ODBC driver in the
# image (msodbcsql18) and network access to the server; see the README.
FROM python:3.12-slim

# unixODBC is required to build/run pyodbc
RUN apt-get update \
    && apt-get install -y --no-install-recommends unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["schema-scout"]
CMD ["demo", "--large"]
