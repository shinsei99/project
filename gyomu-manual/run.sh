#!/bin/bash
cd "$(dirname "$0")"
mkdir -p logs
exec python3 -m http.server 8521 --bind 0.0.0.0 \
    >> logs/stdout.log 2>> logs/stderr.log
