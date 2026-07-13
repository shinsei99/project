#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角屋(横堤)モータープール 配置図ビューア
 - 車室レイアウトは template.html に固定
 - 空き状況（契約者・賃料等）は起動/再読込の度に Dropbox のレントロールxlsxから取得
"""
import http.server, socketserver, json, webbrowser, threading, datetime, os

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, "template.html")
XLSX = ("/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/"
        "（★必読★）新共有フォルダ/物件・管理/レントロール一覧（駐車場他）.xlsx")
SHEET = "角屋（横堤）モータープール"
PORT = 8522


def _s(v):
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y/%m/%d")
    return str(v).replace("　", " ").strip()


def build_data():
    """xlsxを毎回読み込み、区画No→占有状況の辞書を作る"""
    from openpyxl import load_workbook
    wb = load_workbook(XLSX, data_only=True)
    ws = wb[SHEET]
    data = {}
    for r in range(3, ws.max_row + 1):
        raw_no = ws.cell(r, 1).value
        if raw_no is None:
            continue
        try:
            no = int(raw_no)
        except (ValueError, TypeError):
            continue
        genkyo = _s(ws.cell(r, 2).value)
        who = _s(ws.cell(r, 3).value)
        kubun = _s(ws.cell(r, 4).value)
        chin = ws.cell(r, 5).value
        ho = ws.cell(r, 6).value
        keiyakubi = _s(ws.cell(r, 7).value)
        if genkyo == "空室" or not who:
            data[no] = {"v": 1}
        elif "オーナー" in who:
            data[no] = {"o": 1}
        else:
            data[no] = {"n": who, "k": kubun, "chin": chin, "ho": ho, "d": keiyakubi}
    return data


def render():
    tpl = open(TEMPLATE, encoding="utf-8").read()
    try:
        data = build_data()
        note = "自動反映"
    except Exception as e:
        data = {}
        note = "⚠ xlsx読込エラー: %s" % e
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__UPDATED__", "%s（%s）" % (stamp, note))
    return html


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return
        body = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = "http://localhost:%d" % PORT
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("配置図サーバー起動: %s  （Ctrl+Cで終了）" % url)
        print("レントロール: %s" % XLSX)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n終了しました。")
