"""検閲バリデーションエンジン（コアロジック）。

3レイヤーで4者間（行政正解/謄本/重説/契約書）の齟齬をあぶり出し、
CheckResult のリストを生成する。

  ① 入力齟齬     … 書類間・謄本間の文字/数値ミスマッチ
  ② 宅建業法      … 業法40条(契約不適合2年)・38条(違約金2割)・反社/手付
  ③ 建築基準法    … 行政データ突合・セットバック敷地算入の検算
"""

from __future__ import annotations

from models.legal_check_data import (
    CAT_BUILDING,
    CAT_INPUT,
    CAT_LAW,
    STATUS_NA,
    STATUS_NG,
    STATUS_OK,
    CheckResult,
    LegalCrossCheckData,
)

# 浮動小数の許容誤差（面積・率の比較）
_AREA_TOL = 0.01   # ㎡
_RATE_TOL = 0.01   # %


def _fmt_area(v) -> str:
    if v in (None, "", 0, 0.0):
        return ""
    return f"{float(v):.2f}㎡"


def _fmt_pct(v) -> str:
    if v in (None, "", 0, 0.0):
        return ""
    return f"{float(v):g}%"


def _norm_str(s) -> str:
    return str(s or "").replace(" ", "").replace("　", "").strip()


# ============================================================
# ① 入力齟齬レイヤー
# ============================================================
def _check_input(data: LegalCrossCheckData) -> list[CheckResult]:
    results: list[CheckResult] = []
    reg = data.registry
    exp = data.explanation
    con = data.contract

    # --- 地番（謄本 vs 重説 vs 契約書） ---
    results.append(_cmp_text(
        CAT_INPUT, "地番", reg.chiban,
        exp.get("chiban", ""), con.get("chiban", ""),
        advice_ng="地番が書類間で不一致です。物件の同一性に関わるため謄本に合わせて訂正してください。",
    ))

    # --- 家屋番号 ---
    if reg.has_building or exp.get("kaoku_number") or con.get("kaoku_number"):
        results.append(_cmp_text(
            CAT_INPUT, "家屋番号", reg.kaoku_number,
            exp.get("kaoku_number", ""), con.get("kaoku_number", ""),
            advice_ng="家屋番号が不一致です。建物の特定に関わるため謄本どおりに訂正してください。",
        ))

    # --- 地積（土地面積、小数点2桁まで一致） ---
    results.append(_cmp_area(
        CAT_INPUT, "地積（土地面積）", reg.land_area,
        exp.get("land_area"), con.get("land_area"),
        advice_ng="土地面積が謄本の地積と一致しません。登記面積どおりに訂正してください。",
    ))

    # --- 床面積／専有面積 ---
    results.append(_cmp_area(
        CAT_INPUT, "床面積（専有面積）", reg.floor_area,
        exp.get("floor_area"), con.get("floor_area"),
        advice_ng="建物（専有）面積が謄本と一致しません。登記面積どおりに訂正してください。",
    ))

    # --- 名義人 vs 売主 ---
    seller_exp = exp.get("seller_raw", "")
    seller_con = con.get("seller_raw", "")
    owner = _norm_str(reg.owner_name)
    if owner or seller_exp or seller_con:
        # 売主表記に所有者氏名が含まれるかで判定（住所込みの揺れを吸収）
        def _match(seller: str) -> bool:
            s = _norm_str(seller)
            return bool(owner) and owner in s
        ng = bool(owner) and ((seller_exp and not _match(seller_exp))
                              or (seller_con and not _match(seller_con)))
        results.append(CheckResult(
            category=CAT_INPUT, item="所有者名義 vs 売主",
            admin_value=f"📄謄本所有者: {reg.owner_name}",
            explanation_value=seller_exp, contract_value=seller_con,
            status=(STATUS_NG if ng else (STATUS_OK if owner else STATUS_NA)),
            advice=("謄本の所有権登記名義人と売主が一致しません。第三者売買や相続未登記の"
                    "可能性があります。登記名義を確認してください。" if ng else ""),
        ))

    # --- 日付の一致（契約日/説明日/ローン承認期日） ---
    cd, ed = con.get("contract_date", ""), exp.get("explain_date", "")
    if cd or ed:
        ng = bool(cd and ed and _norm_str(cd) != _norm_str(ed))
        results.append(CheckResult(
            category=CAT_INPUT, item="契約日／説明日",
            admin_value="", explanation_value=ed, contract_value=cd,
            status=(STATUS_NG if ng else (STATUS_OK if (cd and ed) else STATUS_NA)),
            advice=("契約書の契約締結日と重説の説明日が食い違っています。"
                    "重説は契約前の説明が原則です。日付を確認してください。" if ng else ""),
        ))

    return results


# ============================================================
# ② 宅建業法レイヤー
# ============================================================
def _check_law(data: LegalCrossCheckData) -> list[CheckResult]:
    results: list[CheckResult] = []
    con = data.contract
    pro = data.seller_is_pro

    # --- 業法40条: 契約不適合の通知期間「引渡しから2年未満」制限の禁止 ---
    months = con.get("nonconformity_months")
    if months is not None:
        # 売主が宅建業者の場合、2年(24か月)未満に制限する特約は無効（買主に不利）
        ng = pro and months < 24
        results.append(CheckResult(
            category=CAT_LAW, item="契約不適合責任の通知期間（業法40条）",
            admin_value=("売主=宅建業者: 引渡しから2年以上必須" if pro else "売主=個人: 制限なし"),
            explanation_value="", contract_value=f"{months}か月",
            status=(STATUS_NG if ng else STATUS_OK),
            advice=(f"売主が宅建業者の場合、契約不適合責任の通知期間を2年未満（現在{months}か月）"
                    "に短縮する特約は宅建業法40条違反で無効です。「引渡しから2年」に修正してください。"
                    if ng else ""),
        ))

    # --- 業法38条: 違約金（損害賠償予定額）が売買代金の20%超は禁止 ---
    price = con.get("sale_price")
    penalty = con.get("penalty_amount")
    if pro and price and penalty:
        ratio = penalty / price * 100 if price else 0
        ng = ratio > 20.0 + _RATE_TOL
        results.append(CheckResult(
            category=CAT_LAW, item="違約金・損害賠償予定額（業法38条）",
            admin_value="売主=宅建業者: 売買代金の20%以内",
            explanation_value="",
            contract_value=f"{penalty:,.0f}円（代金比 {ratio:.1f}%）",
            status=(STATUS_NG if ng else STATUS_OK),
            advice=(f"違約金が売買代金の20%（{price*0.2:,.0f}円）を超えています（現在 {ratio:.1f}%）。"
                    "宅建業法38条により20%を超える部分は無効です。減額してください。" if ng else ""),
        ))

    # --- 反社会的勢力排除条項 ---
    has_anti = con.get("has_antisocial_clause")
    if has_anti is not None:
        results.append(CheckResult(
            category=CAT_LAW, item="反社会的勢力排除条項",
            admin_value="記載必須（標準）",
            explanation_value="", contract_value=("あり" if has_anti else "なし"),
            status=(STATUS_OK if has_anti else STATUS_NG),
            advice=("反社会的勢力排除条項が見当たりません。標準条項として必ず記載してください。"
                    if not has_anti else ""),
        ))

    # --- 手付解除（倍額償還／倍返し）の文言 ---
    has_dbl = con.get("has_double_return")
    if has_dbl is not None:
        results.append(CheckResult(
            category=CAT_LAW, item="手付解除（倍額償還）の文言",
            admin_value="売主からの解除は倍額償還が原則",
            explanation_value="", contract_value=("記載あり" if has_dbl else "記載なし"),
            status=(STATUS_OK if has_dbl else STATUS_NG),
            advice=("売主からの手付解除における「倍額償還（倍返し）」の文言が確認できません。"
                    "手付解除条項を確認してください。" if not has_dbl else ""),
        ))

    return results


# ============================================================
# ③ 建築基準法・都市計画法レイヤー
# ============================================================
def _check_building(data: LegalCrossCheckData) -> list[CheckResult]:
    results: list[CheckResult] = []
    adm = data.admin
    exp = data.explanation

    # --- 用途地域（行政正解 vs 重説） ---
    if adm.use_district or exp.get("use_district"):
        ng = bool(adm.use_district and exp.get("use_district")
                  and _norm_str(adm.use_district) != _norm_str(exp.get("use_district")))
        results.append(CheckResult(
            category=CAT_BUILDING, item="用途地域",
            admin_value=f"🌐{adm.use_district}（{adm.source}）",
            explanation_value=exp.get("use_district", ""), contract_value="",
            status=(STATUS_NG if ng else (STATUS_OK if adm.use_district and exp.get("use_district") else STATUS_NA)),
            advice=(f"行政調査では「{adm.use_district}」ですが、重説では「{exp.get('use_district')}」"
                    "になっています。重大な説明義務違反になるため即座に修正してください。" if ng else ""),
        ))

    # --- 指定建ぺい率 ---
    results.append(_cmp_pct(
        CAT_BUILDING, "指定建ぺい率", adm.building_coverage, exp.get("building_coverage"),
        adm.source,
        advice_ng="建ぺい率が行政の指定値と一致しません。隣セルへの誤記入やタイポの可能性があります。",
    ))

    # --- 指定容積率 ---
    results.append(_cmp_pct(
        CAT_BUILDING, "指定容積率", adm.floor_area_ratio, exp.get("floor_area_ratio"),
        adm.source,
        advice_ng="容積率が行政の指定値と一致しません。隣セルへの誤記入やタイポの可能性があります。",
    ))

    # --- セットバックの敷地算入バグ検算 ---
    sb = exp.get("setback_area")
    calc_site = exp.get("calc_site_area")
    reg_land = data.registry.land_area or exp.get("land_area")
    if sb and reg_land:
        expected = round(float(reg_land) - float(sb), 2)
        if calc_site is not None:
            ng = abs(float(calc_site) - expected) > _AREA_TOL
            # 謄本面積のまま（引き忘れ）かを判定
            forgot = abs(float(calc_site) - float(reg_land)) <= _AREA_TOL
            results.append(CheckResult(
                category=CAT_BUILDING, item="セットバック後の算定敷地面積",
                admin_value=f"📄謄本地積 {float(reg_land):.2f}㎡ − SB {float(sb):.2f}㎡ = {expected:.2f}㎡",
                explanation_value=f"{float(calc_site):.2f}㎡", contract_value="",
                status=(STATUS_NG if ng else STATUS_OK),
                advice=(f"セットバック面積{float(sb):.2f}㎡が建ぺい率・容積率の算定敷地から"
                        + ("引かれていません（謄本面積のまま計算されています）。" if forgot
                           else "正しく差し引かれていません。")
                        + f"算定敷地面積を{expected:.2f}㎡に訂正してください。" if ng else ""),
            ))
        else:
            results.append(CheckResult(
                category=CAT_BUILDING, item="セットバック後の算定敷地面積",
                admin_value=f"要確認: 謄本地積 {float(reg_land):.2f}㎡ − SB {float(sb):.2f}㎡ = {expected:.2f}㎡",
                explanation_value="（算定敷地面積の記載を確認できず）", contract_value="",
                status=STATUS_NA,
                advice="セットバックの記載がありますが、算定敷地面積の記載を確認できませんでした。"
                       f"建ぺい率・容積率は{expected:.2f}㎡を基準に算定されているか確認してください。",
            ))

    return results


# ============================================================
# 比較ヘルパー
# ============================================================
def _cmp_text(cat, item, admin, exp, con, advice_ng) -> CheckResult:
    vals = [v for v in (admin, exp, con) if _norm_str(v)]
    if len(vals) < 2:
        status = STATUS_NA
    else:
        uniq = {_norm_str(v) for v in (admin, exp, con) if _norm_str(v)}
        status = STATUS_OK if len(uniq) == 1 else STATUS_NG
    return CheckResult(
        category=cat, item=item,
        admin_value=str(admin or ""), explanation_value=str(exp or ""),
        contract_value=str(con or ""), status=status,
        advice=(advice_ng if status == STATUS_NG else ""),
    )


def _cmp_area(cat, item, admin, exp, con, advice_ng) -> CheckResult:
    nums = [float(v) for v in (admin, exp, con) if v not in (None, "", 0, 0.0)]
    if len(nums) < 2:
        status = STATUS_NA
    else:
        status = STATUS_OK if (max(nums) - min(nums)) <= _AREA_TOL else STATUS_NG
    return CheckResult(
        category=cat, item=item,
        admin_value=_fmt_area(admin), explanation_value=_fmt_area(exp),
        contract_value=_fmt_area(con), status=status,
        advice=(advice_ng if status == STATUS_NG else ""),
    )


def _cmp_pct(cat, item, admin, exp, source, advice_ng) -> CheckResult:
    have = [v for v in (admin, exp) if v not in (None, "", 0, 0.0)]
    if len(have) < 2:
        status = STATUS_NA
    else:
        status = STATUS_OK if abs(float(admin) - float(exp)) <= _RATE_TOL else STATUS_NG
    admin_disp = _fmt_pct(admin)
    if admin_disp and source:
        admin_disp = f"🌐{admin_disp}（{source}）"
    return CheckResult(
        category=cat, item=item,
        admin_value=admin_disp, explanation_value=_fmt_pct(exp),
        contract_value="", status=status,
        advice=(advice_ng if status == STATUS_NG else ""),
    )


# ============================================================
# エントリポイント
# ============================================================
def validate(data: LegalCrossCheckData) -> list[CheckResult]:
    """3レイヤーを実行し、結果を data.results に格納して返す。"""
    results: list[CheckResult] = []
    results += _check_input(data)
    results += _check_law(data)
    results += _check_building(data)
    data.results = results
    return results
