# presentation-review

研究発表の**練習動画（または音声）をレビューし、先輩研究者目線のフィードバックを `Advice.md` にまとめる** Codex / Claude 共通の Agent Skills リポジトリです。

文字起こし・原稿との突き合わせ・スライド時間配分の実測・抑揚/話速/ポーズの音響解析を一通り行い、「どこを・どう直すか」を時刻つきで具体的に指摘します。学位審査・学会発表・フェローシップ面接などの練習を想定しています。

> English summary is at the bottom of this file.

## できること

| 観点 | 内容 |
|---|---|
| 時間 | 実測時間と制限時間の比較。原稿にタイムスタンプがあれば計画 vs 実測の差分表 |
| 内容 | 文字起こしと原稿の差分。意味が反転する言い間違い、説明が崩れた箇所、書き言葉の混入、主述のねじれ |
| 話し方 | 冒頭の入り、一文の長さ、明瞭度の確認候補、埋め草。誤変換だけで発音の問題は断定しない |
| 韻律 | ピッチの変動幅・毎分の均質性、話速と「最速の文」の内容、1.5 秒超の「ためる」ポーズの有無と位置 |
| 仕上げ | 想定質問 5–6 問、次回練習のチェックリスト。2 回目以降は前回からの改善差分 |

音声抽出・文字起こし・韻律解析はローカルツールで実行します。初回は依存パッケージやモデルをダウンロードします。レビュー生成時に扱う文字起こしや画像の送信・保存は、利用する Codex / Claude 環境のデータ設定に従います。

## フォルダ構成

```
presentation-review/
├── SKILL.md                      # Codex / Claude 共通の手順書
├── agents/
│   └── openai.yaml               # Codex の表示名・呼び出し例
├── scripts/
│   └── prosody_analysis.py       # 韻律解析（ピッチ・音量・話速・ポーズ）
├── assets/
│   └── advice_template.md        # Advice.md の雛形
├── examples/
│   └── prosody_output.example.json  # 解析スクリプトの出力例（合成音声）
├── README.md
├── LICENSE
└── .gitignore
```

## 動作要件

- macOS（Apple Silicon）。文字起こしに `mlx-whisper` を使うため
- [ffmpeg](https://ffmpeg.org/)（`brew install ffmpeg`）
- [uv](https://docs.astral.sh/uv/)（`brew install uv`）。Python 依存はスクリプト冒頭のインライン指定から自動解決されます
- ローカルのファイル・シェル・画像表示ツールを使える Codex CLI / Codex アプリ、Claude Code、または同等の Agent Skills 対応環境

Apple Silicon 以外の環境では、`SKILL.md` の文字起こしコマンドを `openai-whisper` や `faster-whisper` に読み替えてください。出力に `segments` 配列を含む JSON が得られれば、韻律解析スクリプトはそのまま使えます。

## インストール

### Codex

このリポジトリを任意の場所に置き、同名のスキルが未登録であることを確認してから、リポジトリのルートで次を実行します。コピーを増やさず、更新をそのまま反映できます。

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$(pwd)" "$HOME/.agents/skills/presentation-review"
```

既に同名のスキルがある場合は上書きせず、既存の登録先を確認してください。特定プロジェクトだけで使う場合は、リンク先を `<project>/.agents/skills/presentation-review` にします。

Codex の次のターンから `$presentation-review` で呼び出せます。表示されない場合は Codex を再起動してください。保存場所とシンボリックリンクの対応は [OpenAI 公式ドキュメント](https://learn.chatgpt.com/docs/build-skills) に準拠しています。

### Claude Code

ユーザー全体で使う場合:

```bash
git clone https://github.com/<you>/presentation-review ~/.claude/skills/presentation-review
```

特定プロジェクトだけで使う場合は `<project>/.claude/skills/presentation-review` に置きます。

### Claude.ai / Claude Desktop

このフォルダを zip にして、設定の Skills からアップロードします。

## 使い方

練習動画を置いたフォルダで Codex / Claude に依頼します。Codex でスキルを明示する例:

```text
$presentation-review rehearsal_v3.mov をレビューして。制限時間は10分、原稿は script.md。
```

自然な文章での依頼にも対応します。

```
練習動画 rehearsal_v3.mov を見てフィードバックして。制限時間は 10 分。
原稿は script.md にあります。
```

```
前回の Advice.md と比べて、今回の練習で改善したか評価して。
```

```
この音声の抑揚と話速だけ評価して。
```

生成物は動画と同じフォルダに保存されます。

- `Advice.md` レビュー本体
- `transcript_<動画名>.txt` 文字起こし
- `yyyymmdd_presentation_review/` 抽出音声・フレーム・文字起こし JSON・韻律解析 JSON。再実行時は `_rerun02` 等で区別し、更新前のレビューも保管

録音を直接聴けない環境では、明瞭度や言い間違いを確認候補として扱います。音声のみならスライド遷移、原稿なしなら原稿との差分は未確認として示します。

## 解析スクリプトを単体で使う

```bash
# 20261027 は実行開始時のローカル日付に置き換える。既存なら _rerun02 等を付ける。
mkdir 20261027_presentation_review
ffmpeg -y -i rehearsal.mov -ar 16000 -ac 1 -c:a pcm_s16le 20261027_presentation_review/audio.wav
uv run scripts/prosody_analysis.py 20261027_presentation_review/audio.wav whisper_output.json > 20261027_presentation_review/prosody.json
uv run scripts/prosody_analysis.py --help
```

主な出力項目:

| キー | 意味 |
|---|---|
| `pitch.sd_st` | ピッチ標準偏差（半音）。4 前後で文単位の抑揚は十分、2 以下は単調 |
| `pitch.range_st_5_95` | ピッチの 5–95% レンジ（半音）。12 前後が目安 |
| `per_minute[]` | 毎分のピッチ変動・音量変動。どの分も同じ値なら「全部同じメロディー」 |
| `speaking_rate.fastest_segments` | 最速の文。内容と突き合わせると「一番大事な所が一番速い」が見つかる |
| `pauses_acoustic.longest` | 長いポーズの時刻。スライド境界や原稿の演出指示と照合する |

出力例は `examples/prosody_output.example.json` を参照してください（合成音声なので数値自体に意味はありません）。

## カスタマイズ

- 韻律の解釈基準（話速 7 文字/秒、ピッチ SD 4 半音など）は `SKILL.md` の「韻律の解釈基準」に書いてあります。英語発表など前提が変わる場合はここを調整してください
- `Advice.md` の章立ては `assets/advice_template.md` を編集して変えられます

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。

---

## English summary

**presentation-review** is an Agent Skill for Codex and Claude that reviews a recorded practice talk and writes senior-researcher-style feedback to `Advice.md`. It transcribes the recording (mlx-whisper), diffs it against the script, measures time per slide, and runs an acoustic prosody analysis (pitch variability, speaking rate, pauses) with `scripts/prosody_analysis.py`. Audio processing runs locally; handling of transcript text and images during review follows your agent environment's data settings.

Requirements: macOS on Apple Silicon, `ffmpeg`, `uv`. On other platforms swap mlx-whisper for `openai-whisper` or `faster-whisper`; the prosody script only needs a whisper-style JSON with a `segments` list.

For Codex, symlink this repository into `~/.agents/skills/presentation-review` and invoke `$presentation-review`. For Claude Code, clone into `~/.claude/skills/presentation-review`. Then ask e.g. "Review my practice video rehearsal.mov, time limit 10 min, script in script.md." The interpretation thresholds in `SKILL.md` are rough guidance for Japanese talks; adapt them to the speaker, language, and recording conditions.
