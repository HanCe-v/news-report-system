"""Grok API を呼び出して生成AI関連ニュースレポートを生成する."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

XAI_API_KEY = os.environ["XAI_API_KEY"]
API_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-3-fast"

# --- 曜日別テーマ定義 (変更3 + 変更4) ---
DAY_THEMES = {
    0: {  # 月曜
        "theme": "画像生成（ComfyUI、SD、LoRA）",
        "categories": ["ComfyUI", "LoRA", "NSFW画像生成", "その他"],
        "topic_guidance": "ComfyUI、Stable Diffusion、LoRA学習、画像生成ワークフローに関するトピックを優先的に取り上げてください。",
        "source_priority": "Hacker News、Reddit r/MachineLearning を優先してください。",
    },
    1: {  # 火曜
        "theme": "動画・音声（GPT-SoVITS、音声クローン）",
        "categories": ["TTS", "NSFW動画生成", "その他"],
        "topic_guidance": "GPT-SoVITS、音声クローン、TTS音声合成、動画生成に関するトピックを優先的に取り上げてください。",
        "source_priority": "Hacker News、Reddit r/MachineLearning を優先してください。",
    },
    2: {  # 水曜
        "theme": "AI×クリエイティブ制作（小説執筆、シナリオ制作）",
        "categories": ["その他", "Claude Code", "MCP"],
        "topic_guidance": "AIを活用した小説執筆、シナリオ制作、クリエイティブライティングに関するトピックを優先的に取り上げてください。",
        "source_priority": "Hacker News、Reddit r/MachineLearning を優先してください。",
    },
    3: {  # 木曜
        "theme": "Claude Code活用法（開発テクニック、CLAUDE.md設計）",
        "categories": ["Claude Code", "MCP", "その他"],
        "topic_guidance": "Claude Code、CLAUDE.md設計、AI開発テクニック、コーディングアシスタントに関するトピックを優先的に取り上げてください。",
        "source_priority": "Zennのトレンド記事を優先してください。また、Hacker News、Reddit r/MachineLearning も参照してください。",
    },
    4: {  # 金曜
        "theme": "LLM・AI基盤＋ツール（Claude/GPT/Gemini、MCP）",
        "categories": ["Claude Code", "MCP", "その他"],
        "topic_guidance": "Claude、GPT、Gemini等のLLMアップデート、MCP、AI開発ツールに関するトピックを優先的に取り上げてください。",
        "source_priority": "Hacker News、Reddit r/MachineLearning を優先してください。",
    },
}

# 全カテゴリ（バリデーション用）
ALL_CATEGORIES = {
    "NSFW画像生成", "NSFW動画生成", "Claude Code",
    "ComfyUI", "TTS", "LoRA", "MCP", "その他",
}


def get_day_theme():
    """今日のJST曜日に基づくテーマを返す."""
    jst = timezone(timedelta(hours=9))
    weekday = datetime.now(jst).weekday()  # 0=月, 4=金
    return DAY_THEMES.get(weekday)


def build_system_prompt(theme_info, previous_topics_json=None):
    """曜日テーマ・重複排除を反映したSYSTEM_PROMPTを構築."""
    dedup_section = ""
    if previous_topics_json:
        dedup_section = f"""
【過去の報告済みトピック】
{previous_topics_json}

上記は既に報告済みです。
以下のルールで今日のトピックを生成してください：
- 報告済みトピックと同一のテーマは、「新しい事実や数値の変化」がある場合のみ取り上げる
- その場合も「○○に続報：△△が判明」のように差分であることを明示する
- 新しい事実がないテーマは完全にスキップする
- 結果としてトピックが0件でも構わない
"""

    theme_section = ""
    source_section = ""
    if theme_info:
        theme_section = f"""
**本日の重点テーマ**: {theme_info['theme']}
{theme_info['topic_guidance']}
"""
        source_section = f"""
**情報ソース優先指定**: {theme_info['source_priority']}
"""

    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y年%m月%d日")
    yesterday_str = (datetime.now(jst) - timedelta(days=1)).strftime("%Y年%m月%d日")

    return f"""\
あなたは生成AI市場専門の技術ニュース収集AIです。
**今日は{today_str}です。** {yesterday_str}〜{today_str}の最新ニュースのみを対象にしてください。
古い記事（1週間以上前のもの）は絶対に含めないでください。URLの日付も確認し、最新のものだけを選んでください。
信頼できる公式・技術メディアのみを厳選し、**以下のJSON形式のみで出力**してください。他の説明文、挨拶、Markdown、```json は一切出力しないこと。JSONが不正にならないよう厳密に守ってください。
{theme_section}
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

**優先ソース**：Anthropic公式、Stability AI公式、ComfyUI GitHub、Hugging Face、TechCrunch、The Verge、Reuters、arXiv
{source_section}{dedup_section}
出力は厳密にこのJSONのみ：
{{
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "topics": [
    {{
      "title": "ニュースタイトル（日本語）",
      "category": "カテゴリ（NSFW画像生成 / NSFW動画生成 / Claude Code / ComfyUI / TTS / LoRA / MCP / その他 のいずれか1つ厳密に）",
      "importance": 1〜10の整数,
      "summary": "2〜3文の正確な要約（日本語）",
      "url": "完全なソースURL",
      "insight": "開発者・ユーザーへの影響と具体的な活用ポイント（日本語、1〜2文）"
    }}
  ],
  "overall_summary": "全体の1〜2文まとめ（日本語）"
}}"""


def build_user_prompt(theme_info):
    """曜日テーマを反映したUSER_PROMPTを構築."""
    if theme_info:
        return f"今日のテーマは「{theme_info['theme']}」です。このテーマを中心に、過去24時間の生成AI関連ニュースTOP10を収集し、指定のJSONで出力してください。"
    return "過去24時間の生成AI関連ニュースTOP10を収集し、指定のJSONで出力してください。"


def get_past_report_urls():
    """S3から直近7日分のレポートを取得し、既出URLリストを返す（変更1 第1段階）."""
    s3_bucket = os.environ.get("S3_BUCKET")
    aws_region = os.environ.get("AWS_REGION")
    if not s3_bucket or not aws_region:
        print("S3_BUCKET/AWS_REGION not set, skipping URL dedup")
        return set(), None

    try:
        import boto3
        s3 = boto3.client("s3", region_name=aws_region)

        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst)
        urls = set()
        previous_day_topics = None

        for days_ago in range(1, 8):
            d = today - timedelta(days=days_ago)
            key = f"reports/dev/{d.strftime('%Y-%m-%d')}.json"
            try:
                obj = s3.get_object(Bucket=s3_bucket, Key=key)
                data = json.loads(obj["Body"].read().decode("utf-8"))
                for topic in data.get("topics", []):
                    if topic.get("url"):
                        urls.add(topic["url"])
                if days_ago == 1:
                    previous_day_topics = json.dumps(
                        data.get("topics", []), ensure_ascii=False, indent=2
                    )
            except s3.exceptions.NoSuchKey:
                continue
            except Exception as e:
                print(f"Warning: failed to fetch {key}: {e}")
                continue

        print(f"Dedup: found {len(urls)} past URLs from up to 7 days")
        return urls, previous_day_topics
    except ImportError:
        print("boto3 not available, skipping dedup")
        return set(), None
    except Exception as e:
        print(f"Warning: S3 dedup failed: {e}")
        return set(), None


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

    for i, t in enumerate(report["topics"]):
        for key in ("title", "category", "importance", "summary", "url", "insight"):
            if key not in t:
                raise ValueError(f"Topic {i} missing key: {key}")
        if t["category"] not in ALL_CATEGORIES:
            print(f"Warning: Topic {i} has unknown category '{t['category']}', setting to 'その他'")
            t["category"] = "その他"
        if not isinstance(t["importance"], int) or not 1 <= t["importance"] <= 10:
            t["importance"] = max(1, min(10, int(t["importance"])))


def main():
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y-%m-%d")

    # 曜日テーマ取得
    theme_info = get_day_theme()
    if theme_info:
        print(f"Today's theme: {theme_info['theme']}")
    else:
        print("No theme for today (weekend?)")

    # S3から過去レポート取得（重複排除用）
    past_urls, previous_day_topics = get_past_report_urls()

    # プロンプト構築
    system_prompt = build_system_prompt(theme_info, previous_day_topics)
    user_prompt = build_user_prompt(theme_info)

    print(f"Calling Grok API ({MODEL}) with web_search for {today}...")
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "temperature": 0.2,
            "instructions": system_prompt,
            "input": [
                {"role": "user", "content": user_prompt},
            ],
            "tools": [{"type": "web_search"}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()

    # /v1/responses の output から text を抽出
    raw_text = ""
    for item in result.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    raw_text += content.get("text", "")
    print(f"Response received ({len(raw_text)} chars)")

    report = extract_json(raw_text)

    # 第1段階: URL重複排除
    if past_urls:
        original_count = len(report.get("topics", []))
        report["topics"] = [
            t for t in report.get("topics", [])
            if t.get("url") not in past_urls
        ]
        removed = original_count - len(report["topics"])
        if removed > 0:
            print(f"Dedup: removed {removed} topics with duplicate URLs")

    report["date"] = today
    report["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    validate_report(report)

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"report.json generated: {len(report['topics'])} topics")


if __name__ == "__main__":
    main()
