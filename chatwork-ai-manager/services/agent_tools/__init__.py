"""共通Tool層。

Claude（QA/自動解析/定時処理）が使う「安全なラッパー関数」を一元管理する。
構造:  Claude → agent_tool.py(CLI) or 直接import → ここのTool関数 → 既存service → DB

各Tool関数は JSON シリアライズ可能な dict/list を返す（agent_tool.py が JSON 出力する）。
REGISTRY は「実装済みToolの唯一の真実」。System Prompt はこれから生成するので、
存在しないToolをClaudeに説明することが構造的に起きない。
"""
from services.agent_tools import (
    address_tools,
    chatwork_image_tools,
    chatwork_tools,
    dev_tools,
    file_tools,
    drive_tools,
    gis_tools,
    knowledge_tools,
    law_tools,
    progress_tools,
    project_tools,
    reinfolib_tools,
    stats_tools,
    streetview_tools,
    task_tools,
    web_image_tools,
)

# name -> {func, desc, usage}
REGISTRY = {
    # ---- Knowledge ----
    "kb_search": {
        "func": knowledge_tools.kb_search,
        "desc": (
            "資料を全文検索。**kinds で見に行く棚を選べる**（省略すると自社書類だけ）。\n"
            "      自社（既定）… レントロール/管理物件台帳/全ファイル一覧/業務マニュアル/社内ツール\n"
            "      法令 … 国交省・国税庁・個人情報保護委員会の一次資料（最新版・そのまま根拠にできる）\n"
            "        原状回復ガイドライン / 賃貸住宅標準契約書 / マンション標準管理規約 /\n"
            "        長期修繕計画GL / 賃貸住宅管理業法 解釈運用・FAQ / サブリースGL /\n"
            "        宅建業法 解釈運用（令和8年4月施行版）/ インボイスQ&A / 電子帳簿保存法 一問一答\n"
            "      判例 … RETIO（不動産適正取引推進機構）機関誌の裁判例・紛争事例 10年分\n"
            "      本 … 蔵書68冊（★発行年に注意。古い本は考え方だけ使い、法律・数値は引かない）\n"
            "      ★**制度・法律・原状回復・税・トラブルの質問では、必ず kinds を指定して引き直すこと。**\n"
            "        自社書類だけでは『うちのやり方』しか出てこず、根拠を示せない。\n"
            "        答えるときは資料名とページ（出典）をそのまま添える"
        ),
        "usage": ('kb_search {"query":"メゾンドール都島 501 契約者","limit":12}\n'
                  '      例(法令): kb_search {"query":"原状回復 経過年数 負担割合","kinds":"法令"}\n'
                  '      例(判例): kb_search {"query":"更新拒絶 正当事由","kinds":"判例"}\n'
                  '      例(両方): kb_search {"query":"敷金 返還","kinds":"法令,判例"}'),
    },
    "kb_read_document": {
        "func": knowledge_tools.kb_read_document,
        "desc": "指定ファイルをその場で読む（未索引のスキャン画像PDFはclaude visionでOCR）。"
                "kb_searchでヒットしないが全ファイル一覧・フォルダ構成等でフルパスが分かっている資料"
                "（申込書・契約書等のスキャンPDF）に使う。ユーザーに手動確認を促す前にまずこれで読み、"
                "内容から直接回答する。読んだ内容は索引にも自動登録され、次回からkb_searchでも見つかる",
        "usage": 'kb_read_document {"path":"/Users/apple/Library/CloudStorage/.../801・P1_森田将悟(2023.10.15~)/連絡先通・申込書・保証会社.pdf"}',
    },
    # ---- Chatwork ----
    "chatwork_search": {
        "func": chatwork_tools.chatwork_search,
        "desc": "過去のChatworkメッセージをキーワード検索（room_id省略で全ルーム）",
        "usage": 'chatwork_search {"keyword":"見積","room_id":null,"limit":20}',
    },
    "chatwork_get_messages": {
        "func": chatwork_tools.chatwork_get_messages,
        "desc": "指定ルームの直近メッセージを取得",
        "usage": 'chatwork_get_messages {"room_id":12345678,"limit":30}',
    },
    "chatwork_post_message": {
        "func": chatwork_tools.chatwork_post_message,
        "desc": "AI専用アカウントからChatworkへ投稿（post_modeにより自動送信/確認待ち。AI投稿と分かる接頭辞が付く）",
        "usage": 'chatwork_post_message {"room_id":12345678,"body":"...","reason":"依頼","to_account_ids":"87654321"}',
    },
    # ---- Chatwork画像検索・再送信（過去に投稿された写真を探して送る。TASK-20260827-002） ----
    "chatwork_image_search": {
        "func": chatwork_image_tools.chatwork_image_search,
        "desc": "過去にChatworkへ投稿され、claude visionで解析済みの画像をタイトル/物件名/"
                "ルーム名/ファイル名/解析結果本文のキーワードで検索する（画像本体はまだ取得しない）。"
                "タイトルは画像投稿の前後に投稿された会話メッセージ（場所・案件名の説明文）も踏まえて"
                "自動で付けたもの（例:「花園町駅前駐輪場」）。同一室・同一ファイル名で撮影時刻が近い"
                "重複投稿は代表1件にまとめて返す（duplicate_count>1で分かる）。"
                "「○○の外観写真を表示して」のように過去の実物写真を求められたら、まずこれで探す。"
                "戻り値の room_id/file_id を chatwork_image_fetch に渡すと実際に送れる",
        "usage": 'chatwork_image_search {"keyword":"クリスタルコート66 外観","limit":10}',
    },
    "chatwork_image_fetch": {
        "func": chatwork_image_tools.chatwork_image_fetch,
        "desc": "chatwork_image_search でヒットした画像をChatworkから再取得し、送信用の"
                "image_token を発行する（streetview_lookupと同じ流れ）。実際に送るには"
                "戻り値の image_token を chatwork_send_web_image / line_send_web_image に渡す",
        "usage": 'chatwork_image_fetch {"room_id":12345678,"file_id":987}',
    },
    "chatwork_image_set_title": {
        "func": chatwork_image_tools.chatwork_image_set_title,
        "desc": "chatwork_images の1件のtitleを手動で設定/上書きする。"
                "画像投稿の前後の会話から物件名・案件名が判明しているのに、"
                "自動解析ではtitleが空のまま（不明）だった画像を後から埋めるのに使う",
        "usage": 'chatwork_image_set_title {"room_id":349546270,"file_id":2145187954,"title":"花園町駅前駐輪場"}',
    },
    "chatwork_image_delete": {
        "func": chatwork_image_tools.chatwork_image_delete,
        "desc": "Chatworkに間違えて投稿された画像を削除する。「この写真を削除して」と言われたら"
                "まず chatwork_image_search / 直近のやり取りの引用解決で room_id/file_id を特定し、"
                "これを呼ぶ。ただし**Chatwork APIには他人が投稿したファイルを消す手段が無い**"
                "（削除できるのは投稿者本人＝このAI自身のメッセージのみ。仕様上の制約）。"
                "投稿者が社員本人の場合は ok:false が返るので、reason/hint（投稿者名・"
                "手動削除の案内）をそのまま利用者に伝えること。Chatwork本体からは消えないが、"
                "このBotの検索・再送信の対象からは自動で除外される",
        "usage": 'chatwork_image_delete {"room_id":349546270,"file_id":2145187954}',
    },
    # ---- ファイル送付（社内資料をChatworkへ添付） ----
    "chatwork_send_file": {
        "func": file_tools.chatwork_send_file,
        "desc": "社内共有フォルダのファイルをChatworkへ**添付送信**する。"
                "「資料を送って」「図面ください」と言われたら、パスを案内するのではなく"
                "**これで実際に送る**。送信元は社内共有フォルダ配下に限定・5MBまで・"
                "送信は記録されLINEへ通知される。送れないときは理由が返るので、"
                "その理由を利用者にそのまま伝えてパスを案内すること",
        "usage": 'chatwork_send_file {"room_id":12345678,"path":"/Users/apple/Library/CloudStorage/.../間取図面(新)/か/グランビルド岩城/グランビルド岩城3F.jpg","message":"3階の間取図をお送りします","requester":"塚本"}',
    },
    "drive_resolve": {
        "func": drive_tools.drive_resolve,
        "desc": "Googleドライブの共有リンクから、このMacにある実体の場所（絶対パス）を割り出す。"
                "★チャットに drive.google.com のURLが貼られたら、**URLを直接開こうとしないこと**。"
                "非公開なので必ず401になる。まずこれで場所に直してから、"
                "kb_read_document などで中身を読む。フォルダなら中のファイル名も返る。"
                "複数のURLをまとめて渡してよい（本文をそのまま渡せばIDを拾う）。"
                "found=false は、このMacに同期されていないか、別会社のもの",
        "usage": 'drive_resolve {"url":"https://drive.google.com/drive/folders/1KeDIIHB4GvJ3D2dwHg0JcCTDEEUfGdjL"}',
    },
    "find_files": {
        "func": file_tools.find_files,
        "desc": "共有フォルダからファイル名の一部で実体を探す（絶対パス・サイズ・保管フォルダを返す）。"
                "「○○の図面を送って」のように名前しか分からないときは、まずこれで探してから"
                "chatwork_send_file に path を渡す。**archived=true は削除予定フォルダなので、"
                "同じ資料で archived=false があれば必ずそちらを送る**。"
                "sendable=false はサイズ超過で送れないもの",
        "usage": 'find_files {"name":"グランビルド岩城","limit":20}',
    },
    "chatwork_can_send_file": {
        "func": file_tools.chatwork_can_send_file,
        "desc": "そのファイルが送れるかだけ先に確認する（実際には送らない）。"
                "サイズ超過や共有フォルダ外を、送る前に見分けるのに使う",
        "usage": 'chatwork_can_send_file {"path":"/Users/apple/Library/CloudStorage/.../物件資料/か/グランビルド岩城.xls"}',
    },
    "find_sendable_files": {
        "func": file_tools.find_sendable_files,
        "desc": "候補パスをまとめて判定し、送れるもの／送れないもの（理由つき）に仕分ける。"
                "kb_searchや全ファイル一覧で複数の候補が出たときに、まずこれで絞る",
        "usage": 'find_sendable_files {"paths":["/…/グランビルド岩城3F.jpg","/…/グランビルド岩城.xls"]}',
    },
    # ---- TODO ----
    "task_search": {
        "func": task_tools.task_search,
        "desc": "TODOを検索（keyword/assignee/status/room_idで絞り込み）。作成前の重複確認に使う。"
                "複数件を一覧で答えるときは、返り値の formatted（担当者ごとにグループ化＋状態アイコンで"
                "整形済みの文字列。定時TODO確認と同じ見た目）をそのまま回答本文に使うこと",
        "usage": 'task_search {"keyword":"資料確認","assignee":"田中","status":null}',
    },
    "task_create": {
        "func": task_tools.task_create,
        "desc": "TODOを作成。依頼者/担当者/期限/発生元メッセージを保存。同内容の未完了TODOがあれば重複作成しない",
        "usage": 'task_create {"content":"○○資料を確認","assignee_name":"田中","requester":"鈴木","due_date":"2026-08-16","room_id":12345678,"source_message_id":"...","reason":"..."}',
    },
    "task_update": {
        "func": task_tools.task_update,
        "desc": "既存TODOを更新（期限変更・担当者変更・内容修正など）。新規作成ではない",
        "usage": 'task_update {"task_id":12,"due_date":"2026-08-17","reason":"期限変更"}',
    },
    "task_complete": {
        "func": task_tools.task_complete,
        "desc": "TODOを完了にする。根拠メッセージを記録",
        "usage": 'task_complete {"task_id":12,"note":"完了報告あり","evidence_message_id":"..."}',
    },
    "task_progress_update": {
        "func": task_tools.task_progress_update,
        "desc": "TODOの進捗/状態を更新（進行中/確認待ち/保留 等）",
        "usage": 'task_progress_update {"task_id":12,"status":"進行中","note":"確認中","progress":50}',
    },
    # ---- Project ----
    "project_search": {
        "func": project_tools.project_search,
        "desc": "案件を検索（物件名/顧客名）。関連TODOも返す",
        "usage": 'project_search {"keyword":"メゾンドール都島"}',
    },
    "project_update": {
        "func": project_tools.project_update,
        "desc": "案件情報を更新（名前/顧客/状態）",
        "usage": 'project_update {"project_id":3,"status":"完了","reason":"..."}',
    },
    # ---- Progress（定時処理向け・QAでも利用可） ----
    "tasks_needing_attention": {
        "func": progress_tools.tasks_needing_attention,
        "desc": "確認/催促が必要なTODOを抽出（kind: due_soon/overdue/stale/carryover）。"
                "複数件を一覧で答えるときは、返り値の formatted（担当者ごとにグループ化＋状態アイコンで"
                "整形済みの文字列。定時TODO確認と同じ見た目）をそのまま回答本文に使うこと",
        "usage": 'tasks_needing_attention {"kind":"overdue"}',
    },
    # ---- GIS / 地図（管理物件108件の位置情報。座標は国土地理院・DBキャッシュ済み） ----
    "gis_property_search": {
        "func": gis_tools.gis_property_search,
        "desc": "管理物件マスタを検索（物件名/住所/オーナー・分類=自社|管理|仲介|終了・種別=マンション|ビル|駐車場等・エリア）。"
                "位置を扱う質問はまずこれで対象物件を特定する",
        "usage": 'gis_property_search {"keyword":"ベリエール","classification":null,"area":"都島区"}',
    },
    "gis_nearby_properties": {
        "func": gis_tools.gis_nearby_properties,
        "desc": "指定した物件/住所/座標から半径内の管理物件を近い順に返す（距離つき）。"
                "「この物件の近くに自社物件ある？」「半径800mで探して」に使う",
        "usage": 'gis_nearby_properties {"property":"メゾンドール都島","radius_m":1000}',
    },
    "gis_distance": {
        "func": gis_tools.gis_distance,
        "desc": "2地点の距離（物件名でも住所でも可）。球面距離で計算した直線距離",
        "usage": 'gis_distance {"from_property":"大京本社ビル","to_property":"メゾンドール都島"}',
    },
    "gis_area_stats": {
        "func": gis_tools.gis_area_stats,
        "desc": "エリア別の管理物件数（集中している地域を調べる）。group: city/ward/town",
        "usage": 'gis_area_stats {"group":"ward"}',
    },
    "gis_create_map": {
        "func": gis_tools.gis_create_map,
        "desc": "条件に合う物件の地図HTMLを生成（種別で色分け・クリックで詳細）。"
                "center_property＋radius_m で半径円も描ける。extra_points に取引価格等を渡すと重ねられる。"
                "hazard_layers=[\"flood\",\"landslide\",\"hightide\"] でハザードマップポータルのタイルを重ねられる",
        "usage": 'gis_create_map {"area":"都島区","classification":"自社"} '
                 'または {"center_property":"メゾンドール都島","radius_m":1000,"hazard_layers":["flood"]}',
    },
    "gis_land_info": {
        "func": gis_tools.gis_land_info,
        "desc": "指定地点の用途地域/建蔽率/容積率・土砂災害警戒区域該当・近傍の地価公示（国土数値情報／"
                "不動産情報ライブラリ経由の参考値）。重説の水害・土砂災害リスク説明の下調べに使う",
        "usage": 'gis_land_info {"property":"メゾンドール都島"} または {"address":"大阪市都島区中野町1-4-18"}',
    },
    "gis_geocode": {
        "func": gis_tools.gis_geocode,
        "desc": "住所→緯度経度（国土地理院。結果はキャッシュするので同じ住所は再問い合わせしない）",
        "usage": 'gis_geocode {"address":"大阪市都島区中野町1-4-18"}',
    },
    "gis_export_geojson": {
        "func": gis_tools.gis_export_geojson,
        "desc": "条件に合う物件をGeoJSONで書き出す（他のGISツールに渡す標準形式）",
        "usage": 'gis_export_geojson {"classification":"自社","filename":"jisha.geojson"}',
    },
    "gis_market_map": {
        "func": gis_tools.gis_market_map,
        "desc": "管理物件に国交省の取引価格（町名別の中央値）を重ねた地図を作る。"
                "市場データの取得は既存の reinfolib_transactions を内部で再利用している",
        "usage": 'gis_market_map {"prefecture":"大阪府","city_code":"27102","city_name":"大阪市都島区","area":"都島区"}',
    },
    "gis_status": {
        "func": gis_tools.gis_status,
        "desc": "物件マスタと座標の整備状況（何件登録・何件に座標があるか・未取得の一覧）",
        "usage": "gis_status {}",
    },
    "streetview_lookup": {
        "func": streetview_tools.streetview_lookup,
        "desc": "指定地点（住所/物件名/緯度経度のいずれか）の現地画像を取得し、claude visionで"
                "店舗名・看板・目立つ建物名を読み取る。「この場所に何がある？」「1階の店舗名は？」"
                "のように現地の様子・テナント名を目視確認したいときに使う。"
                "google_maps_api_key（要課金設定・未設定）が無い間はGoogleマップの衛星写真"
                "（無料）で代替するため、路上の看板そのものは読めない場合がある旨をnoteで返す。"
                "戻り値の image_token を chatwork_send_web_image / line_send_web_image に渡せば、"
                "取得したその画像自体を送れる（「この画像を送って」と言われたとき用）",
        "usage": 'streetview_lookup {"address":"大阪市都島区中野町1-4-18","question":"1階の店舗名は？"} '
                 'または {"property":"メゾンドール都島"} や {"lat":34.69,"lon":135.52}',
    },
    "streetview_link": {
        "func": streetview_tools.streetview_link,
        "desc": "現地のストリートビューを**人が開いて見る**ためのリンクを返す（住所/物件名/緯度経度）。"
                "「外観を見たい」「現地の様子を確認したい」に使う。撮影年月も一緒に返し、"
                "SVが無い地点なら地図リンクだけ返す。URLにキーは含まないのでそのまま貼ってよい。"
                "⚠️ SV画像をAIに読ませたり、印刷・チラシに載せることは規約上できない（画面で見るのは可）",
        "usage": 'streetview_link {"property":"メゾンドール都島"} または {"address":"大阪市都島区中野町1-4-18"}',
    },
    "streetview_available": {
        "func": streetview_tools.streetview_available,
        "desc": "その地点にストリートビューがあるか・撮影がいつかだけを調べる（無料のmetadata）。"
                "リンクを送る前の確認や、「この写真いつのもの？」に答えるときに使う",
        "usage": 'streetview_available {"address":"大阪市都島区中野町1-4-18","radius":50}',
    },
    "chatwork_send_web_image": {
        "func": web_image_tools.chatwork_send_web_image,
        "desc": "streetview_lookup等でネットから取得した画像（image_token）をChatworkへ添付送信する。"
                "社内共有フォルダのファイルは対象外（それは chatwork_send_file を使う）",
        "usage": 'chatwork_send_web_image {"room_id":12345678,"image_token":"...","message":"取得した衛星写真です"}',
    },
    "line_send_web_image": {
        "func": web_image_tools.line_send_web_image,
        "desc": "streetview_lookup等でネットから取得した画像（image_token）をLINEへ画像メッセージとしてpushする。"
                "user_id省略時はLINE経由の依頼者本人へ自動で送る",
        "usage": 'line_send_web_image {"image_token":"...","message":"取得した衛星写真です"}',
    },
    # ---- 開発（アプリ制作・改修。業務TODOとは別系統） ----
    "dev_task_create": {
        "func": dev_tools.dev_task_create,
        "desc": "アプリ/システムの制作・改修の依頼を開発タスクとして受け付ける（実装は裏で開発エージェントが行う）。"
                "業務のTODO（人への依頼）とは別物なので混同しないこと",
        "usage": 'dev_task_create {"request":"簡単なTODOアプリを作って","title":"TODOアプリ","kind":"NEW_APP"}',
    },
    "dev_task_list": {
        "func": dev_tools.dev_task_list,
        "desc": "開発タスクの一覧（新しい順）。「開発の状況は？」「さっきのアプリ」を特定するのに使う",
        "usage": 'dev_task_list {"status":null,"limit":10}',
    },
    "dev_task_status": {
        "func": dev_tools.dev_task_status,
        "desc": "開発タスク1件の詳細（状態・対象プロジェクト・質問・結果・経過）",
        "usage": 'dev_task_status {"task_id":"TASK-20260817-001"}',
    },
    "dev_task_answer": {
        "func": dev_tools.dev_task_answer,
        "desc": "開発エージェントからの質問（WAITING_USER）にユーザーの回答を渡して続きを再開させる",
        "usage": 'dev_task_answer {"task_id":"TASK-20260817-001","answer":"1でお願いします"}',
    },
    "dev_task_cancel": {
        "func": dev_tools.dev_task_cancel,
        "desc": "開発タスクを中止する",
        "usage": 'dev_task_cancel {"task_id":"TASK-20260817-001","reason":"不要になった"}',
    },
    "dev_task_progress": {
        "func": dev_tools.dev_task_progress,
        "desc": "【開発エージェント専用】自分の進捗を記録する（phase: PLANNING/RUNNING/TESTING）",
        "usage": 'dev_task_progress {"task_id":"TASK-20260817-001","phase":"TESTING","note":"ブラウザ確認中"}',
    },
    # ---- 国交省API（公的な不動産データ） ----
    "reinfolib_cities": {
        "func": reinfolib_tools.reinfolib_cities,
        "desc": "国交省: 都道府県の市区町村コード一覧（取引価格検索の前段）",
        "usage": 'reinfolib_cities {"prefecture":"大阪府"}',
    },
    "reinfolib_transactions": {
        "func": reinfolib_tools.reinfolib_transactions,
        "desc": "国交省: 不動産取引価格情報を都道府県/市区町村・年で集計（相場の客観データ）。"
                "⚠️ city_code は必ず reinfolib_cities で確認してから使う（27102=都島区 / 27122=西成区）",
        "usage": 'reinfolib_transactions {"prefecture":"大阪府","city_code":"27102","year":2024}',
    },
    # ---- 商圏の公的統計（e-Stat・政府統計） ----
    "estat_area_profile": {
        "func": stats_tools.estat_area_profile,
        "desc": "e-Stat: その市区町村の人口・世帯数・1世帯あたり人員・高齢化率・転入転出（社会増減）・"
                "昼夜間人口比率・2040年の将来推計人口。物件名でも住所でも地名でも指定できる。"
                "compare に他の区・市を並べると横並びで比べられる。"
                "「このあたり賃貸需要ある？」「若い世帯は多い？」の客観的な裏付けに使う。"
                "**必ず調査年を添えて答えること**（人口は5年おきの国勢調査）",
        "usage": 'estat_area_profile {"property":"メゾンドール都島"} または '
                 '{"city":"大阪市都島区","compare":["大阪市旭区","大阪市中央区"]}',
    },
    "estat_housing_profile": {
        "func": stats_tools.estat_housing_profile,
        "desc": "e-Stat: その市区町村の総住宅数・空き家数と空き家率・借家率・民営借家の割合・"
                "共同住宅率・着工新設貸家数（新規供給の勢い）・借家1戸あたり延べ面積。"
                "買取や新規管理の判断、オーナーへの提案の根拠に使う。"
                "⚠️ 統計の空き家には募集中の空室も含まれるので、自社の空室率とは別物として説明すること",
        "usage": 'estat_housing_profile {"city":"大阪市都島区","compare":["大阪市旭区"]}',
    },
    "estat_indicator_search": {
        "func": stats_tools.estat_indicator_search,
        "desc": "e-Stat: 上の2つに入っていない指標を項目名から探す（例「外国人」「保育所」「着工」）。"
                "見つけたコードは estat_indicator_value に渡す",
        "usage": 'estat_indicator_search {"keyword":"空き家"}',
    },
    "estat_indicator_value": {
        "func": stats_tools.estat_indicator_value,
        "desc": "e-Stat: estat_indicator_search で見つけた任意の項目の値を取る（複数市区町村の比較・"
                "history=true で年次推移も）。table は population（人口・世帯）/ housing（居住）/ "
                "economy / labor / safety など",
        "usage": 'estat_indicator_value {"codes":["H110202"],"table":"housing","city":"大阪市都島区","history":true}',
    },
    # ---- 住所・郵便番号（日本郵便API） ----
    "zip_lookup": {
        "func": address_tools.zip_lookup,
        "desc": "日本郵便: 郵便番号（3桁以上）やデジタルアドレスから住所を引く。"
                "社内資料の住所は人の入力なので、公式データと突き合わせて確かめるときに使う",
        "usage": 'zip_lookup {"code":"5340024"}',
    },
    "address_to_zip": {
        "func": address_tools.address_to_zip,
        "desc": "日本郵便: 住所から郵便番号を引く（送付書・宛名・重説の住所欄の裏取り）。"
                "⚠️ 番地まで入れると見つからないので、番地は自動で落として引き直している",
        "usage": 'address_to_zip {"address":"大阪市都島区東野田町"}',
    },
    # ---- 法令（e-Gov 法令API・キー不要） ----
    "law_search": {
        "func": law_tools.law_search,
        "desc": "e-Gov: 法令名から法令IDを探す（「宅建業法」のような通称も可）",
        "usage": 'law_search {"title":"宅建業法"}',
    },
    "law_article": {
        "func": law_tools.law_article,
        "desc": "e-Gov: 条番号で現行条文を原文のまま取り出す（例: 宅建業法35条・借地借家法28条）。"
                "法律の質問は記憶で答えず必ずこれで引く。施行日も一緒に返る",
        "usage": 'law_article {"law":"宅地建物取引業法","number":"35"}',
    },
    "law_find_articles": {
        "func": law_tools.law_find_articles,
        "desc": "e-Gov: 条番号が分からないとき、本文にキーワードを含む条を探す",
        "usage": 'law_find_articles {"law":"借地借家法","keyword":"更新拒絶"}',
    },
}


def call(name: str, args: dict):
    if name not in REGISTRY:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return REGISTRY[name]["func"](**(args or {}))
    except TypeError as e:
        return {"ok": False, "error": f"引数エラー: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def catalog() -> str:
    """System Prompt 用のTool一覧テキスト（実装と常に一致）。"""
    lines = []
    for name, meta in REGISTRY.items():
        lines.append(f"- {name}: {meta['desc']}\n    例: python3 agent_tool.py {meta['usage']}")
    return "\n".join(lines)
