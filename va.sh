#!/bin/bash
# Visual Agent — Claude Code がブラウザを見て操作してUIを検証する。./va.sh --help
cd "$(dirname "$0")" && exec /usr/bin/python3 visual_agent.py "$@"
