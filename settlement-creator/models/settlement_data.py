"""決済清算の単一データ構造。

パイプライン全体（重説・評価証明書のパース → 日割り計算 → 売主買主の
符号反転マッピング → 決済案内書Excel出力）でこの `SettlementData` を受け渡しする。

仕様の `SettlementAutoCreateData` に相当する。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date


# 固都税の起算日（地域慣習）
START_MONTH_KANTO = 1   # 関東：1月1日起算
START_MONTH_KANSAI = 4  # 関西：4月1日起算

# 日割りの分母（実務慣習に合わせ365日固定）
DAYS_BASE = 365


@dataclass
class SettlementData:
    """決済案内書作成に必要な全データ。"""

    # ---- 重要事項説明書からパース ----
    sale_price: int = 0            # 売買代金
    deposit: int = 0               # 手付金
    mgmt_fee_monthly: int = 0      # 管理費（月額）
    repair_fee_monthly: int = 0    # 修繕積立金（月額）
    seller_name: str = ""          # 売主氏名
    buyer_name: str = ""           # 買主氏名
    property_location: str = ""    # 物件所在

    # ---- 固定資産税評価証明書（納税通知書）からパース ----
    fixed_asset_tax: int = 0       # 固定資産税相当額（年額）
    city_planning_tax: int = 0     # 都市計画税相当額（年額）
    tax_year_label: str = ""       # 年度表記（例: 令和6年度）

    # ---- 画面入力 ----
    settlement_date: date | None = None    # 決済日（引き渡し日）
    start_month: int = START_MONTH_KANSAI  # 固都税起算月（4=関西 / 1=関東）。既定は4月1日
    next_month_fee: bool = False          # 管理費等の翌月分前払いフラグ

    # ---- 諸費用（任意・手動微調整用） ----
    buyer_brokerage: int = 0       # 買主：仲介手数料
    buyer_registration: int = 0    # 買主：司法書士登記費用（所有権移転）
    seller_brokerage: int = 0      # 売主：仲介手数料
    seller_registration: int = 0   # 売主：司法書士登記費用（抵当権抹消等）

    # ---- 派生値 ----
    @property
    def annual_tax(self) -> int:
        """固都税の年間総額（T）。"""
        return self.fixed_asset_tax + self.city_planning_tax

    @property
    def remaining_price(self) -> int:
        """売買残代金（売買代金 − 手付金）。"""
        return self.sale_price - self.deposit

    @property
    def monthly_fee(self) -> int:
        """管理費＋修繕積立金の月額合計。"""
        return self.mgmt_fee_monthly + self.repair_fee_monthly

    @property
    def region_label(self) -> str:
        return "関西（4月1日起算）" if self.start_month == START_MONTH_KANSAI else "関東（1月1日起算）"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SettlementLine:
    """決済案内書「精算金内訳」テーブルの1行。

    amount は符号付き：プラス＝当日授受される金額、マイナス＝天引き項目。
    """

    label: str           # 項目名
    amount: int          # 符号付き金額（円）
    note: str = ""       # 計算内訳のテキスト


@dataclass
class SettlementDoc:
    """買主用 / 売主用 いずれか一方の決済案内書。"""

    role: str                                   # "買主" / "売主"
    name: str                                   # 宛名
    lines: list[SettlementLine] = field(default_factory=list)
    total_label: str = ""                       # 合計欄のラベル
    notes: list[str] = field(default_factory=list)  # 備考欄（自動文言含む）

    @property
    def total(self) -> int:
        """差引合計額（符号付きの単純合算）。"""
        return sum(l.amount for l in self.lines)
