"""発行企業（自社）情報のプロフィール保存・読み込み。

複数の自社情報を data/issuers.csv に保存し、会社名で呼び出して切り替えられる。
決済案内書・請求書・送金精算書のヘッダーに印字される。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ISSUERS_CSV = DATA_DIR / "issuers.csv"

ISSUER_FIELDS = ["name", "representative", "address", "tel", "fax", "registration_no", "bank"]
ISSUER_LABELS = {
    "name": "会社名",
    "representative": "代表者",
    "address": "住所",
    "tel": "TEL",
    "fax": "FAX",
    "registration_no": "インボイス登録番号",
    "bank": "振込先",
}
EMPTY_ISSUER = {f: "" for f in ISSUER_FIELDS}


def load_issuers() -> pd.DataFrame:
    if ISSUERS_CSV.exists():
        df = pd.read_csv(ISSUERS_CSV, dtype=str).fillna("")
        for f in ISSUER_FIELDS:        # 後方互換: 欠けている列を補う
            if f not in df.columns:
                df[f] = ""
        return df[ISSUER_FIELDS]
    return pd.DataFrame(columns=ISSUER_FIELDS)


def save_issuer(data: dict) -> None:
    """同名の発行企業は上書き保存する。"""
    DATA_DIR.mkdir(exist_ok=True)
    df = load_issuers()
    df = df[df["name"] != data["name"]]
    row = {f: data.get(f, "") for f in ISSUER_FIELDS}
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(ISSUERS_CSV, index=False)


def delete_issuer(name: str) -> None:
    df = load_issuers()
    df = df[df["name"] != name]
    df.to_csv(ISSUERS_CSV, index=False)
