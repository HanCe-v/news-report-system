"""Grok API を呼び出して生成AI関連ニュースレポートを生成する."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from openai import OpenAI

XAI_API_KEY = os.environ["XAI_API_KEY"]
MODEL = "grok-4-1-fast-reasoning"

SYSTEM_PROMPT = """\
あなたは生成AI市場専門の技術ニュース収集AIです。
過去24時間のニュースから信頼できる公式・技術メディアのみを厳選し、**以下のJSON形式のみで出力**してください。他の説明文、挨拶、Markdown、```json は一切出力しないこと。JSONが不正にならないよう厳密に守ってください。

対象トピック（以下すべてをカバー）：
- Claude Codeの最新アップデート・機能追加
- ComfyUI 新機能・ワークフロー改善
- LoRA 学習効率化・新テクニック
- TTS音声合成の進化
- NSFW画像生成ツールの新機能・規制動向
- NSFW動画生成ツールの進展
- MCP関連ニュース
- その他生成AI市場の技術的動向

**AI驚き屋・クリックベイト完全排除ルール（最優先）**：
- 「ヤバイ」「今ヤバイ」「衝撃」「驚愕」「爆誕」など煽りタイトルは一切選択しない
- YouTubeまとめ、個人ブログ、Twitterまとめは除外

**優先ソース**：Anthropic公式、Stability AI公式、ComfyUI GitHub、Hugging Face、TechCrunch、The Verge、Reuters、arXivなど

出力は厳密にこのJSONのみ：
{
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "topics": [
    {
      "title": "ニュースタイトル（日本語）",
      "category": "カテゴリ（NSFW画像生成 / NSFW動画生成 / Claude Code / ComfyUI / TTS / LoRA / MCP / その他 のいずれか1つ厳密に）",
      "importance": 1〜10の整数,
      "summary": "2〜3文の正確な要約（日本語）",
      "url": "完全なソースURL",
      "insight": "開発者・ユーザーへの影響と具体的な活用ポイント（日本語、1〜2文）"
    }
  ],
  "overall_summary": "全体の1〜2文まとめ（日本語）"
}"""

USER_PROMPT = "過去24時間の生成AI関連ニュースTOP10を収集し、指定のJSONで出力してください。"


def extract_json(text: str) -> dict:
    """レスポンスからJSON部分だけを抽出する."""
    # Remove markdown code fence if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(lines)

    # Find the outermost { }
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
        "NSFW画像生成", "NSFW動画生成", "Claude Code",
        "ComfyUI", "TTS", "LoRA", "MCP", "その他",
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
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    client = OpenAI(base_url="https://api.x.ai/v1", api_key=XAI_API_KEY)

    print(f"Calling Grok API ({MODEL}) for {today}...")
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

    # Ensure date and generated_at are correct
    report["date"] = today
    report["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    validate_report(report)

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"report.json generated: {len(report['topics'])} topics")


if __name__ == "__main__":
    main()
