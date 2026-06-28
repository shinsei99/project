"""賃貸契約の精算データ構造。

入居者用（初期費用 精算明細書兼請求書）とオーナー用（初回送金精算書）の
2帳票を、編集可能な明細行リストとして保持する。月額賃料等の自動入力値から
当月日割り・翌月分の標準明細を生成し、ユーザーが自由に追加・修正できる。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date


@dataclass
class RentLine:
    """賃貸明細の1行。amount は符号付き（マイナス＝割引・天引き）。"""

    label: str
    amount: int
    note: str = ""


@dataclass
class RentalData:
    """賃貸初回精算の全データ。"""

    # 基本情報
    property_location: str = ""
    room_number: str = ""
    landlord_name: str = ""      # 貸主（オーナー）
    tenant_name: str = ""        # 借主（入居者）
    move_in_date: date | None = None   # 入居日（当月日割りの起点）

    # 月額（自動入力・日割りと明細生成の元値）
    rent: int = 0               # 家賃
    common_fee: int = 0         # 共益費・管理費
    parking: int = 0            # 駐車場代
    insurance: int = 0          # 火災保険・サポート（月額相当）

    # 一時金（入居者請求の元値）
    deposit: int = 0            # 敷金
    key_money: int = 0          # 礼金
    guarantee_fee: int = 0      # 家賃保証料
    key_exchange: int = 0       # 鍵交換代
    parking_key_money: int = 0  # 駐車場礼金
    remote_fee: int = 0         # リモコン代
    brokerage: int = 0          # 仲介手数料
    brokerage_discount: int = 0 # 仲介手数料の割引額（正の値で入力、明細ではマイナス）

    # オーナー送金精算の元値
    ad_fee: int = 0             # 広告料（AD）：管理会社へ支払い
    owner_brokerage: int = 0    # 仲介手数料（貸主負担分）
    mgmt_fee_rate: float = 5.0  # 集金代行（管理）手数料率（家賃に対する%）

    # 帳票の明細（自動生成後、画面で編集される）
    tenant_items: list[RentLine] = field(default_factory=list)
    owner_items: list[RentLine] = field(default_factory=list)

    # フッター
    payment_due: str = ""       # 支払期限
    required_docs: str = ""     # 必要書類

    @property
    def monthly_total(self) -> int:
        """月額合計（家賃＋共益費＋駐車場＋保険）。"""
        return self.rent + self.common_fee + self.parking + self.insurance

    def as_dict(self) -> dict:
        return asdict(self)
