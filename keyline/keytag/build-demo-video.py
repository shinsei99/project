#!/usr/bin/env python3
"""KeyTagNFC のデモ動画を仕上げる。

やること
  1. 英語（画面上）＋日本語（画面下）の字幕を .ass で作る
  2. 日本語ナレーションを gTTS で合成し、各字幕の開始時刻に置いた1本のWAVにする
  3. 元動画（2.7K/HEVC/628MB・元音声は捨てる）を 720p/H.264 に変換し、字幕を焼き込む

元音声を捨てる理由: 事務所で撮っているため周囲の会話が入っている可能性があり、
公開ページに置く前提だと危ないため。

**このMacに ffmpeg は入っていないが、agent-platform の venv に
imageio-ffmpeg 同梱のバイナリ（7.1・libass/libfreetype 入り）がある**ので、
それを使えば字幕の焼き込みまでできる。サブPCへ渡す必要はない。

    ~/agent-platform/.venv/bin/python keyline/keytag/build-demo-video.py

元動画は git に入らない大きさ（2.7K/HEVC/628MB）なので、**メインPCの
`~/Pictures/GX010219.MP4`** に置いてある。作り直すときはこれを持ってくること。
出力は `.demo-build/`（gitignore）。完成品は gh-pages の
`keytagnfc-support/keytag-nfc-demo.mp4` として公開済み。
"""
import hashlib
import pathlib
import subprocess
import sys
import wave

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path.home() / "Pictures" / "GX010219.MP4"
BUILD = HERE / ".demo-build"          # 出力先（gitignore）
WORK = BUILD / "work"
OUT = BUILD / "keytag-nfc-demo.mp4"
DURATION = 116.85
TAIL = 2.0    # 末尾に最後のフレームを静止で足す秒数。
              # これが無いと最後のナレーション（111.0秒開始・約6秒）が尺の終わりで切れる
RATE = 24000  # ナレーションWAVのサンプリングレート（モノラル16bit）

# (開始, 終了, 英語, 日本語) — 時刻は実際のフレームを見て決めた
CUES = [
    (0.0, 7.5, "A blank, unformatted NFC tag (NTAG213) and an iPhone.",
     "まっさらな未フォーマットのNFCタグ（NTAG213）とiPhoneです。"),
    (7.5, 16.0, "Launching KeyTag on a real iPhone. This app is for iPhone only.",
     "実機のiPhoneでKeyTagを起動します。iPhone専用のアプリです。"),
    (16.0, 31.0, "Registering a key: building name and key name.",
     "鍵を登録します。物件名と鍵の名称を入力します。"),
    (31.0, 47.0, "Then the key number and where it is stored.",
     "続いて鍵番号と、保管している場所を入力します。"),
    (47.0, 61.5, "No server is connected. Everything runs on the device itself.",
     "サーバー連携は設定していません。すべて端末の中だけで動きます。"),
    # ここは枠が4秒しかないので、ナレーションは短く切る（長いと早口になる）
    (61.5, 65.5, 'FIRST PAIRING — tap "Write to tag". iOS opens the NFC scan sheet.',
     "初回ペアリングです。「タグに書き込む」を押します。"),
    (65.5, 72.0, "Holding the blank tag to the top of the iPhone writes the key data to it.",
     "読み取り画面が出たら、まっさらなタグをiPhoneの上端にかざします。"),
    (72.0, 81.5, 'Now reading it back. Tap "Read tag".',
     "次に読み取ります。「タグを読み取る」を押します。"),
    (81.5, 88.0, "The same tag is held to the iPhone, and the app identifies the key.",
     "同じタグをかざすと、どの鍵かが画面に出ます。"),
    (88.0, 101.0, "Lending the key. The borrower and the due date are test data.",
     "鍵を貸し出します。貸出先と返却予定はテスト用のダミーです。"),
    (101.0, 105.5, "The ledger keeps the lending history on the device.",
     "台帳に貸出の履歴が残ります。"),
    (105.5, 111.0, "Returning the key by holding the same tag again.",
     "同じタグをもう一度かざして、返却します。"),
    (111.0, DURATION + TAIL, "The key is available again. All of this works with no server.",
     "貸出可能に戻りました。サーバーが無くても全機能が動きます。"),
]


def ts(t):
    """ASS の時刻表記 H:MM:SS.cc"""
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_ass(path):
    """英語＝画面上・日本語＝画面下。下に4行まとめるとiPhoneが隠れるため分ける。"""
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,Hiragino Sans W6,30,&H00FFFFFF,&H00000000,&H80000000,0,0,1,3,1,8,60,60,26,1
Style: JA,Hiragino Sans W6,34,&H00FFFFFF,&H00000000,&H80000000,0,0,1,3,1,2,60,60,26,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    for start, end, en, ja in CUES:
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},EN,,0,0,0,,{en}\n")
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},JA,,0,0,0,,{ja}\n")
    path.write_text("".join(lines), encoding="utf-8")
    print(f"字幕: {path.name}（{len(CUES)}カット・英語=上 / 日本語=下）")


def to_wav(src, dst, tempo=1.0):
    """mp3 → 24kHz モノラル 16bit WAV。tempo>1 で早口にする（枠に収めるため）。"""
    af = f"atempo={tempo:.3f}" if abs(tempo - 1.0) > 0.001 else "anull"
    subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-af", af,
                    "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(dst)],
                   check=True)


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def build_narration(path):
    """日本語ナレーションを1本のWAVにまとめる（各カットの開始時刻に置く）。"""
    from gtts import gTTS

    total = int((DURATION + TAIL + 1.0) * RATE)
    buf = bytearray(total * 2)          # 全長ぶんの無音（16bit=2バイト）
    for i, (start, end, _en, ja) in enumerate(CUES, 1):
        # 文面が変わったら自動で作り直されるよう、ファイル名に本文のハッシュを入れる
        tag = hashlib.sha1(ja.encode("utf-8")).hexdigest()[:8]
        mp3 = WORK / f"n{i:02d}-{tag}.mp3"
        wav = WORK / f"n{i:02d}-{tag}.wav"
        if not mp3.exists():
            gTTS(text=ja, lang="ja").save(str(mp3))
        to_wav(mp3, wav)
        sec = wav_seconds(wav)
        slot = end - start
        # 枠を1.2秒以上はみ出すなら早口にして収める（最大1.4倍まで）
        if sec > slot + 1.2:
            tempo = min(1.4, sec / (slot + 1.0))
            to_wav(mp3, wav, tempo)
            print(f"  {i:2d}. {sec:.1f}秒 → 枠{slot:.1f}秒に対して長いので "
                  f"{tempo:.2f}倍速 → {wav_seconds(wav):.1f}秒")
            sec = wav_seconds(wav)
        else:
            print(f"  {i:2d}. {sec:.1f}秒 / 枠{slot:.1f}秒")
        with wave.open(str(wav)) as w:
            data = w.readframes(w.getnframes())
        off = int(start * RATE) * 2
        buf[off:off + len(data)] = data

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(buf))
    print(f"ナレーション: {path.name}（{wav_seconds(path):.1f}秒）")


def render(ass, narration):
    """720p/H.264・字幕焼き込み・元音声は捨てる・faststart（Web再生用）。"""
    # tpad で最後のフレームを TAIL 秒ぶん複製してから字幕を焼く。
    # 順番が逆だと、足した静止部分に最後の字幕が乗らない。
    vf = (f"scale=1280:720:flags=lanczos,"
          f"tpad=stop_mode=clone:stop_duration={TAIL},"
          f"subtitles={ass}:fontsdir=/System/Library/Fonts")
    cmd = [FF, "-v", "warning", "-stats", "-y",
           "-i", str(SRC), "-i", str(narration),
           "-map", "0:v:0", "-map", "1:a:0",      # 元音声(0:a)は使わない
           "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "24",
           "-pix_fmt", "yuv420p", "-r", "30",
           "-c:a", "aac", "-b:a", "96k", "-ac", "1",
           "-movflags", "+faststart",
           "-shortest", str(OUT)]
    print("変換中…（数分かかります）")
    subprocess.run(cmd, check=True)


def main():
    if not SRC.exists():
        sys.exit(f"元動画が見つかりません: {SRC}")
    WORK.mkdir(parents=True, exist_ok=True)
    ass = WORK / "subs.ass"
    narration = WORK / "narration.wav"
    write_ass(ass)
    build_narration(narration)
    render(ass, narration)
    mb = OUT.stat().st_size / 1024 / 1024
    print(f"\n完成: {OUT}  {mb:.1f} MB")
    if mb > 50:
        print("⚠️ 50MB超。GitHubに置くなら crf を上げるか尺を詰めること")


if __name__ == "__main__":
    main()
