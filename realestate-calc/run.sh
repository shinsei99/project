#!/bin/bash
cd "$(dirname "$0")"
# 静的PWA。launchdは最小PATHしか渡さないためnode/npxのパスを明示（[[reference-cross-pc-handoff]]）
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
exec npx -y serve -s . -l 8507
