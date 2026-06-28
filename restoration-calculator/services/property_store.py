"""物件（物件名・住所）のプロフィール保存・読み込み。

物件名と住所を data/properties.csv に保存し、物件名で呼び出すと住所が
自動入力されるようにする（発行元プロフィールと同じ仕組み）。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROPERTIES_CSV = DATA_DIR / "properties.csv"

PROPERTY_FIELDS = ["name", "address"]


def load_properties() -> pd.DataFrame:
    if PROPERTIES_CSV.exists():
        df = pd.read_csv(PROPERTIES_CSV, dtype=str).fillna("")
        for f in PROPERTY_FIELDS:
            if f not in df.columns:
                df[f] = ""
        return df[PROPERTY_FIELDS]
    return pd.DataFrame(columns=PROPERTY_FIELDS)


def save_property(data: dict) -> None:
    """同名の物件は上書き保存する。"""
    DATA_DIR.mkdir(exist_ok=True)
    df = load_properties()
    df = df[df["name"] != data["name"]]
    row = {f: data.get(f, "") for f in PROPERTY_FIELDS}
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(PROPERTIES_CSV, index=False)


def delete_property(name: str) -> None:
    df = load_properties()
    df = df[df["name"] != name]
    df.to_csv(PROPERTIES_CSV, index=False)
