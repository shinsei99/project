#!/usr/bin/env python3
"""共通Tool層のCLIディスパッチャ。

Claude（QAエージェント）が Bash からツールを呼ぶための入口:
  python3 agent_tool.py <tool_name> '<JSON引数>'
  python3 agent_tool.py --list          # 実装済みTool一覧（System Prompt生成用）

結果は必ず JSON 1行で標準出力する（エージェントが読み取る）。
内部処理からは services.agent_tools.call(name, args) を直接呼べる（subprocess不要）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.migrate import migrate  # noqa: E402
from services import agent_tools  # noqa: E402


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("--list", "-l"):
        print(agent_tools.catalog())
        return
    name = args[0]
    payload = {}
    if len(args) > 1 and args[1].strip():
        try:
            payload = json.loads(args[1])
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"JSON引数の解析に失敗: {e}"}, ensure_ascii=False))
            return
    migrate()  # DBスキーマ保証（冪等）
    result = agent_tools.call(name, payload)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
