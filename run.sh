#!/usr/bin/env bash
export $(cat .env | xargs) 2>/dev/null || true
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
