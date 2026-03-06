"""Grok API を呼び出して金融・経済ニュースレポートを生成する."""
import json
import os
import sys
from datetime import datetime, timezone

from openai import OpenAI

XAI_API_KEY = os.environ["XAI_API_KEY"]
MODEL = "grok-4-1-fast-reasoning"

SYSTEM_PROMPT = """\
あなたは金融・経済市場専門のニュース収集AIです。
過去24時間のニュースから信頼できる公式・金融メディアのみを厳選し、**以下のJSON形式のみで出力**してください。他の説明文、挨拶、Markdown、```json は一切出力しないこと。JSONが不正にならないよう厳密に守ってください。

対象トピック（以下すべてをカバー）：
- FRB・ECB・日銀など主要中央銀行の金融政策
- GDP・雇用統計・CPI・PMIなど主要経済指標
- 主要企業の決算発表・業績見通し
- 為替市場・債券市場の動向
- 原油・金・農産物などコモディティ市場
- 日経平均・TOPIX・日本市場固有の動向
- 金融規制・制度変更・税制改正
- その他グローバル金融市場の重要ニュース

**AI驚き屋・クリックベイト完全排除ルール（最優先）**：
- 「ヤバイ」「今ヤバイ」「衝撃」「驚愕」「爆誕」など煽りタイトルは一切選択しない
- YouTubeまとめ、個人ブログ、Twitterまとめは除外

**優先ソース**：Reuters、Bloomberg、CNBC、Wall Street Journal、日本経済新聞、Financial Times、Fed公式、ECB公式、日銀公式

出力は厳密にこのJSONのみ：
{
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "topics": [
    {
      "title": "ニュースタイトル（日本語）",
      "category": "カテゴリ（金融政策 / 経済指標 / 企業決算 / 為替・債券 / コモディティ / 日本市場 / 規制・制度 / その他 のいずれか1つ厳密に）",
      "importance": 1〜10の整数,
      "summary": "2〜3文の正確な要約（日本語）",
      "url": "完全なソースURL",
      "insight": "投資家・市場関係者への影響と具体的なポイント（日本語、1〜2文）"
    }
  ],
  "overall_summary": "全体の1〜2文まとめ（日本語）"
}"""

USER_PROMPT = "過去24時間の金融・経済ニュースTOP10を収集し、指定のJSONで出力してください。"


def extract_json(text: str) -> dict:
    """レスポンスからJSON部分だけを抽出する."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(lines)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in response: {text[:200]}")
    return json.loads(text[start : end + 1])


def validate_report(report: dict) -> None:
    """スキーマの基本検証."""
    required = {"date", "generated_at", "topics", "overall_summary"}
    missing = required - set(report.keys())
    if missing:
        raise ValueError(f"Missing top-level keys: {missing}")

    valid_categories = {
        "金融政策", "経済指標", "企業決算", "為替・債券",
        "コモディティ", "日本市場", "規制・制度", "その他",
    }
    for i, t in enumerate(report["topics"]):
        for key in ("title", "category", "importance", "summary", "url", "insight"):
            if key not in t:
                raise ValueError(f"Topic {i} missing key: {key}")
        if t["category"] not in valid_categories:
            print(f"Warning: Topic {i} has unknown category '{t['category']}', setting to 'その他'")
            t["category"] = "その他"
        if not isinstance(t["importance"], int) or not 1 <= t["importance"] <= 10:
            t["importance"] = max(1, min(10, int(t["importance"])))


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    client = OpenAI(base_url="https://api.x.ai/v1", api_key=XAI_API_KEY)

    print(f"Calling Grok API ({MODEL}) for finance report {today}...")
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
    )

    raw_text = response.choices[0].message.content
    print(f"Response received ({len(raw_text)} chars)")

    report = extract_json(raw_text)

    report["date"] = today
    report["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    validate_report(report)

    with open("finance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"finance_report.json generated: {len(report['topics'])} topics")


if __name__ == "__main__":
    main()
