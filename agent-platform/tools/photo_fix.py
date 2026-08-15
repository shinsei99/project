"""アイテム: 写真から不要物を消す（photo-inpainter の LaMa をそのまま利用）

同じリポジトリの `photo-inpainter` が LaMa（IOPaint・Apache-2.0）を持っている。
torch込みで .venv が 1.3GB あるため、**こちらに再インストールせず**
向こうの .venv を subprocess で呼ぶ。実測: 1600×1067 の電線消去が CPU で約4秒。

制約（正直に）: LaMa は「どこを消すか」のマスクが要る。マスクを自動で作る手段は
photo-inpainter 側でも人のクリック（SAM）が前提。よってこのアイテムは
**マスクが用意できる場合のみ**使える。物件写真の自動お掃除には、まだ人の指定が要る。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Tuple

NAME = "photo_fix"
LABEL = "写真の不要物消去（LaMa）"
DESCRIPTION = ("写真から電線・電柱・車・家具を消す。完全ローカル・無料。"
               "消す範囲（マスク画像）が必要")

APP_DIR = Path(__file__).resolve().parent.parent.parent / "photo-inpainter"
VENV_PY = APP_DIR / ".venv" / "bin" / "python"

_RUNNER = """
import sys
sys.path.insert(0, {app!r})
from PIL import Image
import numpy as np
from inpainting import inpaint_lama
image = Image.open({image!r}).convert("RGB")
mask = np.array(Image.open({mask!r}).convert("L"))
result = inpaint_lama(image, mask)
result.save({out!r})
print("ok")
"""


def available() -> Tuple[bool, str]:
    if not APP_DIR.exists():
        return False, "photo-inpainter が見つかりません"
    if not VENV_PY.exists():
        return False, "photo-inpainter の .venv が未作成（向こうで run.sh を1度実行）"
    return True, "photo-inpainter の環境を借りて実行します（マスクが必要）"


def inpaint(image_path, mask_path, out_path, timeout: int = 300) -> Path:
    """マスクの白い部分を消して out_path に保存する。"""
    ok, note = available()
    if not ok:
        raise RuntimeError(note)
    script = _RUNNER.format(app=str(APP_DIR), image=str(image_path),
                            mask=str(mask_path), out=str(out_path))
    proc = subprocess.run([str(VENV_PY), "-c", script], capture_output=True,
                          text=True, timeout=timeout, cwd=str(APP_DIR))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "LaMaの実行に失敗").strip()[:400])
    return Path(out_path)
