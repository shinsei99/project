#!/bin/bash
# Claude Code の「目」。詳しくは see.py の先頭、または ./see.sh --help
cd "$(dirname "$0")" && exec /usr/bin/python3 see.py "$@"
