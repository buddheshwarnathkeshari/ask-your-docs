#!/usr/bin/env sh
set -e

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"

echo "Waiting for postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."

# Try to open a TCP connection using Python (portable inside python image)
python - <<PY
import socket, os, sys, time
host = os.getenv("POSTGRES_HOST", "postgres")
port = int(os.getenv("POSTGRES_PORT", "5432"))
timeout = 2
retries = 60
for i in range(retries):
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        print("Postgres is available at {}:{}".format(host, port))
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("Timed out waiting for Postgres at {}:{}".format(host, port), file=sys.stderr)
sys.exit(1)
PY
