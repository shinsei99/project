"""チラシ部隊と部品ライブラリの回帰テスト。

過去に踏んだ事故:
  - `KeyError: 'count'` で工程が丸ごと落ちた
  - LLMにHTMLを書かせていた頃、1枚に230秒かかり毎回どこかが崩れた
    → **部品を組み合わせる方式**に変更。ここではその土台を固定する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agents.flyer_builder import FlyerBuilderAgent, _fallback_layout
from core import blocks


def _deck():
    return {"title": "テスト物件のご案内", "subtitle": "兵庫県加東市",
            "slides": [{"no": 1, "title": "3LDK 5.9万円",
                        "bullets": ["敷金礼金0円", "駐車場1台込み"],
                        "narration": "", "image_prompt": ""}]}


# --- 部品ライブラリ ---------------------------------------------------------

def test_every_block_renders_without_arguments():
    """引数が足りなくても例外にせず、空文字を返すこと。

    LLMの出力は欠けることがある。1つの部品の不備で紙面全部を失わないため。
    """
    for name, func in blocks.BLOCKS.items():
        assert isinstance(func(), str), "%s が文字列を返さない" % name


def test_unknown_block_is_skipped_not_fatal():
    html = blocks.render_page([{"block": "存在しない部品", "x": 1},
                               {"block": "catch", "text": "残るべき文言"}])
    assert "残るべき文言" in html


def test_photo_numbers_resolve_to_files(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    paths = []
    for i in range(3):
        path = tmp_path / ("p%d.png" % i)
        Image.new("RGB", (40, 30), (i * 60, 90, 120)).save(path)
        paths.append(str(path))

    html = blocks.render_page(
        [{"block": "photo_hero", "photo": 1},
         {"block": "photo_grid", "photos": [2, 3], "cols": 2}],
        photos=paths)
    assert html.count("data:image/png;base64,") == 3, "写真が埋め込まれていない"


def test_out_of_range_photo_number_is_ignored(tmp_path):
    html = blocks.render_page([{"block": "photo_hero", "photo": 9}], photos=[])
    assert "<img" not in html


def test_text_is_escaped():
    html = blocks.render_page([{"block": "catch", "text": "<script>危険</script>"}])
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_steps_needs_at_least_two():
    assert blocks.steps(items=["1つだけ"]) == ""
    assert "step" in blocks.steps(items=["警告", "撤去"])


# --- チラシ部隊 -------------------------------------------------------------

def test_fallback_layout_uses_all_available_photos():
    layout = _fallback_layout(_deck(), [Path("a.jpg")] * 5)
    grids = [b for b in layout if b["block"] == "photo_grid"]
    assert grids and len(grids[0]["photos"]) == 4, "残りの写真を使い切っていない"


def test_fallback_layout_without_photos_still_has_content():
    layout = _fallback_layout(_deck(), [])
    assert layout[0]["block"] == "header_band"
    assert any(b["block"] == "bullets" for b in layout)


def test_collect_photos_prefers_uploaded(ctx):
    pytest.importorskip("PIL")
    from PIL import Image

    for i in range(4):
        Image.new("RGB", (32, 32), (200, 30 * i, 30)).save(
            ctx.dir("input") / ("photo_%d.jpg" % i))
    ctx.state["images"] = []

    photos = FlyerBuilderAgent()._collect_photos(ctx)
    assert len(photos) == 4
    assert all("input" in str(p) for p in photos)


def test_flyer_agent_produces_pdf_without_llm(ctx):
    """LLMが使えなくても、雛形の構成でPDFが出ること。"""
    pytest.importorskip("playwright")
    import tools

    ok, _ = tools.flyer.available()
    if not ok:
        pytest.skip("Playwright未導入")

    ctx.state["plan"] = {"title": "テスト物件のご案内", "genre": "promo"}
    ctx.state["deck"] = _deck()
    result = FlyerBuilderAgent().run(ctx)

    assert result.ok, result.error
    pdf = Path(ctx.root) / ctx.state["flyer"]
    assert pdf.exists() and pdf.stat().st_size > 1000


# --- 紙面の型 ---------------------------------------------------------------

def _content():
    return {"kicker": "兵庫県加東市", "catch": "森のログハウス", "title": "3LDK",
            "sub": "敷礼なし", "price": "59,000", "unit": "円 / 月", "lead": "説明文",
            "badges": ["ペット可"], "appeals": [{"title": "A", "text": "a"},
                                               {"title": "B", "text": "b"}],
            "spec_rows": [["間取り", "3LDK"], ["面積", "62.73㎡"]],
            "photos": {"hero": 1, "floorplan": 2, "rooms": [3, 4, 5, 6, 7]},
            "contact": {"tel": "06-0000-0000", "company": "テスト商事"}}


def test_every_template_builds_and_renders():
    """全ての型が、部品として成立する並びを返すこと。

    型は「完成形」なので、1つ壊れると紙面が丸ごと出せなくなる。
    """
    from core import layouts

    for tpl in layouts.all_templates(""):
        layout = layouts.build(tpl["id"], _content())
        assert len(layout) >= 4, "%s の部品が少なすぎる" % tpl["id"]
        for item in layout:
            assert item.get("block") in blocks.BLOCKS, \
                "%s に未知の部品 %s" % (tpl["id"], item.get("block"))
        html = blocks.render_page(layout)
        assert "森のログハウス" in html or "3LDK" in html


def test_floor_plan_is_never_cropped():
    """間取り図は contain（切らない）で置くこと。切ると図面が欠ける。"""
    from core import layouts

    for tid in ("photo_first", "catch_first", "gallery", "split"):
        layout = layouts.build(tid, _content())
        plans = [b for b in _walk(layout)
                 if b.get("block") == "photo_hero" and b.get("caption") == "間取り"]
        assert plans, "%s に間取り図が無い" % tid
        assert all(p.get("fit") == "contain" for p in plans), "%s で図面を切っている" % tid


def _walk(layout):
    for item in layout:
        yield item
        for side in ("left", "right"):
            for child in (item.get(side) or []):
                if isinstance(child, dict):
                    yield child


def test_template_falls_back_when_id_is_unknown():
    from core import layouts

    assert layouts.build("存在しない型", _content())


def test_missing_photos_do_not_break_the_layout():
    from core import layouts

    content = dict(_content())
    content["photos"] = {}
    for tpl in layouts.all_templates(""):
        assert layouts.build(tpl["id"], content)


def test_answer_maps_to_template_id():
    from core import layouts

    assert layouts.id_from_answer("写真主役｜外観を大きく1枚。") == "photo_first"
    assert layouts.id_from_answer("gallery") == "gallery"
    assert layouts.id_from_answer("わからない") == ""


# --- 登録した型 -------------------------------------------------------------

def test_saved_template_keeps_layout_and_swaps_content(tmp_path, monkeypatch):
    """登録した型に別の内容を流し込んでも、並びと寸法が変わらないこと。

    型の値打ちは「並びと寸法」にある。ここが content で書き換わると、
    登録した意味が無くなる。
    """
    from core import layouts, user_templates

    monkeypatch.setattr(user_templates, "STORE", tmp_path / "saved.json")
    content = _content()
    layout = layouts.build("photo_first", content)
    spec = user_templates.save("テスト型", layout, content)

    # 写真の番号は目印になっていること（別の物件で差し替わるため）
    marks = [b for b in spec["layout"] if b.get("block") == "full_photo"]
    assert marks and str(marks[0]["photo"]).startswith("@")
    assert marks[0]["height"] == 112, "寸法は残すこと"

    other = dict(content, catch="別の物件のキャッチ",
                 photos={"hero": 5, "floorplan": 1, "rooms": [2, 3, 4]})
    rebuilt = user_templates.build(spec["id"], other)
    assert [b.get("block") for b in rebuilt] == [b.get("block") for b in layout]
    hero = [b for b in rebuilt if b.get("block") == "full_photo"][0]
    assert hero["photo"] == 5 and hero["height"] == 112


def test_saved_template_drops_blocks_without_photos(tmp_path, monkeypatch):
    """写真が足りない物件に流し込んだとき、空の写真枠を残さないこと。"""
    from core import layouts, user_templates

    monkeypatch.setattr(user_templates, "STORE", tmp_path / "saved.json")
    content = _content()
    spec = user_templates.save("テスト型", layouts.build("photo_first", content), content)

    rebuilt = user_templates.build(spec["id"], dict(content, photos={"hero": 1}))
    assert not [b for b in rebuilt if b.get("block") == "photo_row"]
    assert [b for b in rebuilt if b.get("block") == "full_photo"]


def test_prohibition_pictograms_are_normalized():
    """禁止の紙面に素の記号を混ぜないこと（「自転車OK」に読めてしまう）。"""
    import tools

    assert tools.pictograms.to_prohibition(["bicycle", "car"]) == \
        ["no_bicycle", "no_parking"]
    # 当てが外れたときに意味の違う記号を出さない
    assert tools.pictograms.guess_all("よく分からない依頼文") == []


def test_signage_paper_metrics_scale_with_height():
    """A3は級数も余白も1.41倍になること（紙だけ大きくしても掲示物にならない）。"""
    from core import signage_templates

    a4 = signage_templates.metrics("A4")
    a3 = signage_templates.metrics("A3")
    assert abs(a3["k"] / a4["k"] - 1.414) < 0.01
    assert a3["frame"] > a4["frame"]
    assert signage_templates.metrics("A4_LANDSCAPE")["pw"] == 297


# --- Webページの読み取り ----------------------------------------------------

def test_photo_urls_come_out_of_proxy_links():
    """画像配信の中継URLから、中に埋まっている実URLを取り出せること。

    物件サイトは `image.php?file=<実URLをエンコード>` の形で配信することがある。
    中継URLのまま拾うと拡張子で判定できず、1枚も取れない（実際に0枚になった）。
    """
    import tools

    html = ('<img src="https://image4.homes.jp/smallimg/image.php?file='
            'https%3A%2F%2Fcdn.example.jp%2Fimage%2Frent%2Fabc%2F1_132000.jpg'
            '%3Ft%3D2026&amp;width=640">')
    urls = tools.photos.extract_from_html(html)
    assert any("cdn.example.jp" in u and u.endswith(".jpg") for u in urls), urls


def test_thumbnail_and_full_size_are_merged():
    """同じ写真のサムネと原寸が両方あるとき、大きい方だけを残すこと。"""
    import tools

    html = ('<img src="https://x.jp/a_100x75.jpg">'
            '<img src="https://x.jp/a_1200x900.jpg">')
    urls = tools.photos.extract_from_html(html)
    assert urls == ["https://x.jp/a_1200x900.jpg"]


def test_logos_and_icons_are_excluded():
    import tools

    html = ('<img src="https://x.jp/logo.png"><img src="https://x.jp/icon_menu.png">'
            '<img src="https://x.jp/gaikan.jpg">')
    assert tools.photos.extract_from_html(html) == ["https://x.jp/gaikan.jpg"]


def test_html_to_text_keeps_table_cells_apart():
    """条件表がつながって読めなくならないこと。

    いきなりタグを消すと「賃料5.9万円管理費3000円」と連結して、
    AIが値を取り違える。
    """
    import tools

    html = "<table><tr><th>賃料</th><td>5.9万円</td></tr>" \
           "<tr><th>管理費</th><td>3000円</td></tr></table>"
    text = tools.webread.to_text(html)
    assert "賃料　5.9万円" in text.replace(" ", "　")
    assert "5.9万円管理費" not in text.replace(" ", "").replace("　", "")


def test_researcher_survives_pruning_when_brief_has_url():
    """URLがある依頼で調査工程が外れないこと。

    外れると事実が無いまま紙面を作り、物件名も賃料も「＿＿＿」になる（実際に起きた）。
    """
    from core.pipeline import Pipeline
    from core.context import JobContext

    ctx = JobContext(brief="https://example.com/room/1 のPRチラシを作って",
                     options={}, job_id="test-prune-url")
    ctx.state["plan"] = {"deliverables": ["flyer"], "genre": "promo",
                         "research_depth": "urls"}
    pipeline = Pipeline()
    kept = pipeline._prune_by_plan(ctx, set(pipeline.agents))
    assert "researcher" in kept


# --- 紙面1枚は司令塔が直接作る -----------------------------------------------

def test_single_flyer_job_drops_manuscript_agents():
    """チラシ1枚の依頼で、原稿系の3工程が動かないこと。

    企画構成→高速チェッカー→中間調整はスライド原稿を書いて直しているだけで、
    チラシの文言はチラシビルダーが調査結果から直接書いている。
    実測で60秒使って紙面に1文字も届いていなかった。
    """
    from core.pipeline import Pipeline
    from core.context import JobContext

    ctx = JobContext(brief="この物件のPRチラシを作って", options={},
                     job_id="test-direct-mode")
    ctx.state["plan"] = {"deliverables": ["flyer"], "genre": "promo"}
    kept = Pipeline()._prune_by_plan(ctx, set(Pipeline().agents))
    assert kept == {"orchestrator", "researcher", "flyer", "legal", "acceptance"}


def test_video_job_keeps_the_full_line():
    """動画まで作る依頼では、原稿の工程が残ること（原稿が要る成果物なので）。"""
    from core.pipeline import Pipeline
    from core.context import JobContext

    ctx = JobContext(brief="解説動画を作って", options={}, job_id="test-full-line")
    ctx.state["plan"] = {"deliverables": ["mp4"], "genre": "deck"}
    kept = Pipeline()._prune_by_plan(ctx, set(Pipeline().agents))
    assert {"planner", "voice", "video"} <= kept


def test_flyer_builds_without_a_manuscript(ctx):
    """原稿が無くても、計画と調査結果から紙面の中身を組み立てられること。"""
    from agents.flyer_builder import _deck_from_plan

    ctx.state["research"] = {"findings": [{"question": "賃料", "answer": "5.9万円"}]}
    deck = _deck_from_plan({"title": "テスト物件のご案内"}, ctx)
    assert deck and deck["slides"][0]["bullets"] == ["5.9万円"]


def test_legal_reads_the_flyer_text_not_the_manuscript(ctx):
    """法務が、実際に紙に載る文言を検査対象にすること。"""
    from agents.legal import _deck_from_flyer

    ctx.state["flyer_content"] = {"catch": "驚きの安さ", "title": "3LDK",
                                  "lead": "必ず値上がりします",
                                  "spec_rows": [["賃料", "5.9万円"]]}
    deck = _deck_from_flyer(ctx)
    text = " ".join(deck["slides"][0]["bullets"]) + deck["title"]
    assert "必ず値上がりします" in text and "5.9万円" in text


def test_flyer_waits_for_the_researcher():
    """チラシビルダーが調査を待つこと。

    待たずに走ると、写真0枚・条件なしの紙面ができる（実際にそうなった）。
    事実と写真はこの部隊の材料なので、揃う前に始めてはいけない。
    """
    from agents.flyer_builder import FlyerBuilderAgent

    waits = set(FlyerBuilderAgent.depends_on) | \
        set(FlyerBuilderAgent.depends_if_present)
    assert "researcher" in waits


def test_leftover_space_is_absorbed_by_the_last_bar():
    """紙面の下に残った隙間を、最後の帯が吸うこと。

    余白の付け替え（上に足して下から引く）だけでは高さが変わらず、
    見た目が1mmも改善しなかった。**高さを直接決める**必要がある。
    """
    from core import flyer_build

    html = "<style>.body{}</style><div class='body'><div class='contactbar'>x</div></div>"
    layout = [{"block": "contact_bar"}]

    class FakeFlyer:
        @staticmethod
        def measure_page(doc, paper):
            return {"ratio": 0.95, "last_height_mm": 40.0, "scale": 0.7}

    import tools
    original = tools.flyer
    tools.flyer = FakeFlyer
    try:
        fixed = flyer_build._absorb_gap(html, layout, "A4")
    finally:
        tools.flyer = original
    assert "height:" in fixed and "justify-content:center" in fixed
    # 40mm + (1-0.95)*297/0.7 ≈ 61mm
    assert "61." in fixed or "60." in fixed, fixed[:160]


def test_full_page_is_left_alone():
    """すでに埋まっている紙面には手を入れないこと。"""
    from core import flyer_build

    class FakeFlyer:
        @staticmethod
        def measure_page(doc, paper):
            return {"ratio": 0.995, "last_height_mm": 40.0, "scale": 1.0}

    import tools
    original = tools.flyer
    tools.flyer = FakeFlyer
    try:
        html = "<style></style>"
        assert flyer_build._absorb_gap(html, [{"block": "contact_bar"}], "A4") == html
    finally:
        tools.flyer = original


# --- 写真の解像度 -----------------------------------------------------------

def test_small_images_are_not_downloaded(tmp_path):
    """紙面に使えない小さい画像を取り込まないこと。

    254x169 のサムネイルが混ざり、それがメイン写真になってA4全幅に
    引き伸ばされた（実効30dpi）。容量では弾けない（20KB以上あった）。
    """
    pytest.importorskip("PIL")
    from PIL import Image
    import tools

    class FakeResp:
        def __init__(self, data):
            self.content = data
            self.headers = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    import io

    def make(width, height):
        buf = io.BytesIO()
        Image.new("RGB", (width, height), (120, 120, 120)).save(buf, format="JPEG")
        # 20KB以上にして、容量では弾けない状況を作る
        return buf.getvalue() + b"\x00" * (25 * 1024)

    responses = [FakeResp(make(254, 169)), FakeResp(make(1000, 667))]
    import types

    fake_requests = types.SimpleNamespace(get=lambda *a, **k: responses.pop(0))
    original = sys.modules.get("requests")
    sys.modules["requests"] = fake_requests
    try:
        saved = tools.photos.download(["http://x/a.jpg", "http://x/b.jpg"], tmp_path)
    finally:
        if original is not None:
            sys.modules["requests"] = original
    assert len(saved) == 1 and saved[0]["width"] == 1000


def test_low_resolution_hero_is_swapped(tmp_path):
    """メイン写真が小さすぎるとき、一番大きい写真と入れ替えること。"""
    pytest.importorskip("PIL")
    from PIL import Image
    from agents.flyer_builder import _fix_hero_resolution

    paths = []
    for width, height in ((300, 200), (1600, 1067), (1000, 667)):
        path = tmp_path / ("p%d.jpg" % width)
        Image.new("RGB", (width, height), (200, 200, 200)).save(path)
        paths.append(path)

    class Dummy:
        def log(self, *a, **k):
            pass

    picked = _fix_hero_resolution(Dummy(), None,
                                  {"hero": 1, "floorplan": 3, "rooms": [2]}, paths)
    assert picked["hero"] == 2, picked
    assert 1 in picked["rooms"], "元のメインはサブへ回す"


def test_floor_plan_is_filled_in_from_the_labels():
    """判別済みの間取り図が、紙面に必ず回ること。

    「3番＝間取り図」と分かっているのに文言生成が floorplan を落とし、
    間取り図の無いチラシが出た（実際に出た）。
    """
    from agents.flyer_builder import _fill_photo_roles

    class Dummy:
        def log(self, *a, **k):
            pass

    labels = {"1": "外観", "3": "間取り図", "4": "洋室", "8": "LDK"}
    picked = _fill_photo_roles(Dummy(), None, {"hero": 1, "rooms": [8, 4]}, labels, 10)
    assert picked["floorplan"] == 3
    assert 3 not in picked["rooms"], "間取り図を室内写真に混ぜない"


def test_hero_is_never_the_floor_plan():
    """間取り図がメイン写真になってしまわないこと。"""
    from agents.flyer_builder import _fill_photo_roles

    class Dummy:
        def log(self, *a, **k):
            pass

    labels = {"1": "間取り図", "2": "外観", "3": "LDK"}
    picked = _fill_photo_roles(Dummy(), None, {"hero": 1}, labels, 3)
    assert picked["floorplan"] == 1 and picked["hero"] == 2


# --- 読みやすさ・法定表示 ---------------------------------------------------

def test_text_on_dark_bars_is_readable():
    """濃い帯の上の文字が、必ず読める明るさになること。

    緑の帯に緑の賃料を出して「読みにくい」と指摘された。
    色相は保ったまま明度だけ上げる（白を混ぜると色がくすんで力が落ちる）。
    """
    from core import blocks, palettes

    for item in palettes.all_palettes():
        on_ink = blocks.readable_on(item["accent"], item["ink"])
        assert blocks._contrast(on_ink, item["ink"]) >= 4.4, item["id"]


def test_legal_sees_the_contact_bar():
    """法務が、帯に入っている商号・所在地・免許番号を読めること。

    渡していなかったため、紙面に入っているのに「一切表示されていない」と
    重大リスクで上がった（誤検出）。
    """
    from agents.legal import _deck_from_flyer

    class Ctx:
        state = {"flyer_content": {
            "catch": "森の音で", "title": "3LDK",
            "contact": {"company": "テスト商事", "address": "大阪市…",
                        "tel": "06-0000-0000", "license": "大阪府知事(1)第1号"}}}

    text = " ".join(_deck_from_flyer(Ctx())["slides"][0]["bullets"])
    for word in ("テスト商事", "大阪市", "06-0000-0000", "大阪府知事(1)第1号"):
        assert word in text, word


def test_portrait_photos_are_kept(tmp_path):
    """縦長の写真を落とさないこと。

    幅で判定していたため 427x640 のような縦位置の室内写真が全滅し、
    1物件の写真10枚がすべて捨てられた。室内は縦で撮ることが多い。
    """
    pytest.importorskip("PIL")
    import io
    import types
    from PIL import Image
    import tools

    class FakeResp:
        def __init__(self, data):
            self.content = data
            self.headers = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    def make(width, height):
        buf = io.BytesIO()
        Image.new("RGB", (width, height), (100, 140, 100)).save(buf, format="JPEG")
        return buf.getvalue() + b"\x00" * (25 * 1024)

    # 360x480 の室内写真も残すこと（600で切ったら紙面から室内が消えた）
    responses = [FakeResp(make(427, 640)), FakeResp(make(254, 169)),
                 FakeResp(make(360, 480))]
    original = sys.modules.get("requests")
    sys.modules["requests"] = types.SimpleNamespace(get=lambda *a, **k: responses.pop(0))
    try:
        saved = tools.photos.download(
            ["http://x/a.jpg", "http://x/b.jpg", "http://x/c.jpg"], tmp_path)
    finally:
        if original is not None:
            sys.modules["requests"] = original
    assert [s["height"] for s in saved] == [640, 480], saved


# --- 事実に無い設備を載せない -----------------------------------------------

def test_features_not_in_the_source_are_removed():
    """調べた事実に出てこない設備を紙面から外すこと。

    「オートロック」が勝手に入った。物件に無い設備を広告に載せるのは
    不当表示（景表法）で、印刷して配ると取り返しがつかない。
    """
    from agents.flyer_builder import _verify_features

    class Ctx:
        brief = ""
        state = {"page_text": "バルコニー、エアコン、クロゼット、エレベーター、駐輪場、"
                              "宅配ボックス、CATV、光ファイバー、即入居可、防犯カメラ、"
                              "駅徒歩10分以内、都市ガス、敷金・礼金不要、閑静な住宅地"}

    class Agent:
        def log(self, *a, **k):
            pass

    data = {"icons": ["オートロック", "宅配ボックス", "エレベーター", "追焚き機能"],
            "badges": ["南向き", "即入居可"]}
    _verify_features(Agent(), Ctx(), data)
    assert data["icons"] == ["宅配ボックス", "エレベーター"]
    assert data["badges"] == ["即入居可"]


def test_features_without_an_icon_become_text_tags():
    """絵の無い項目をアイコン行に混ぜないこと。

    「駅徒歩7分以内」「3沿線以上利用可」に絵が無く、そこだけ抜けて
    高さが揃わず崩れた。絵の無いものは文字のタグに回す。
    """
    from core import layouts

    content = {"icons": ["駅徒歩7分以内", "オートロック", "宅配ボックス"],
               "badges": ["敷金不要"], "spec_rows": [["賃料", "1円"]],
               "photos": {"hero": 1}, "contact": {"tel": "1"}}
    built = layouts.build("gallery", content)
    icons = [b for b in built if b.get("block") == "icon_row"][0]["items"]
    tags = [b for b in built if b.get("block") == "badge_row"][0]["items"]
    assert "駅徒歩7分以内" not in icons and "駅徒歩7分以内" in tags
    assert icons == ["オートロック", "宅配ボックス"]
