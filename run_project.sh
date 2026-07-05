#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found on PATH." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm was not found on PATH." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm install
npm run build

python app.py > /tmp/neurosync-backend.log 2>&1 &
npm start > /tmp/neurosync-frontend.log 2>&1 &

echo "Started backend and frontend."
echo "Backend: http://localhost:5001"
echo "Frontend: http://localhost:3000"
