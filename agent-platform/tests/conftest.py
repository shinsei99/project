"""テスト共通の前提。

テストでは外部APIを一切叩かない。ルーティングを存在しないプロバイダに固定して
必ず縮退経路（雛形生成）を通す。出力先も一時フォルダへ逃がす。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["AP_ROUTE_REASONING"] = "none"
os.environ["AP_ROUTE_LONGCONTEXT"] = "none"
os.environ["AP_ROUTE_FAST"] = "none"
os.environ["AP_ROUTE_LIGHT"] = "none"
os.environ["AP_ROUTE_TOOLS"] = "none"
# 道具（Web・ファイル読み）は claude CLI 経由で実際に外部へ出るため、テストでは必ず切る。
# これを忘れると pytest が本物のCLIを呼び出して何分も返ってこない（実際に踏んだ）。
os.environ["AP_AGENT_TOOLS"] = "off"
os.environ["AP_ALLOW_WEB"] = "0"
os.environ["AP_IMAGE_BACKEND"] = "stub"
os.environ["AP_TTS_BACKEND"] = "silent"
os.environ["AP_OUTPUT_DIR"] = tempfile.mkdtemp(prefix="agent-platform-test-")

import pytest  # noqa: E402


@pytest.fixture
def ctx(request):
    """テストごとに別のジョブフォルダを使う。

    JobContext の既定のジョブIDは秒単位の日時なので、同じ秒に走ったテストが
    同じフォルダを共有し、片方が置いたファイルをもう片方が拾ってしまう
    （実際にテストが単体では通るのに全体では落ちる、という形で踏んだ）。
    """
    from core.context import JobContext

    return JobContext(brief="テスト用の依頼です", options={"slide_count": 3},
                      job_id="test-%s" % request.node.name[:60])
