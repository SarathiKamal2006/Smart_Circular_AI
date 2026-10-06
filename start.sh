#!/usr/bin/env bash
# Starts backend (:8000) and frontend (:5173). Install dependencies first (see README).
set -e
cd "$(dirname "$0")"
(cd backend && python -m uvicorn app.main:app --reload --port 8000) &
BACK=$!
trap "kill $BACK 2>/dev/null" EXIT
cd frontend && npm run dev
