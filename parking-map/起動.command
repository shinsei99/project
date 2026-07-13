#!/bin/bash
cd "$(dirname "$0")"
# 既存の8522を止めてから起動
lsof -ti :8522 2>/dev/null | xargs kill -9 2>/dev/null
python3 serve.py
