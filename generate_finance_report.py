"""Grok API を呼び出して金融・経済ニュースレポートを生成する."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

XAI_API_KEY = os.environ["XAI_API_KEY"]
API_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-3-fast"
MODEL_SEARCH = "grok-4.20-beta-latest-non-reasoning"

# --- 曜日別テーマ定義 (変更2 + 変更4) ---
DAY_THEMES = {
    0: {  # 月曜
        "theme": "中央銀行・金融政策",
        "categories": ["金融政策", "その他"],
        "topic_guidance": "FRB、ECB、日銀など主要中央銀行の金融政策決定、発言、議事録に関するトピックを優先的に取り上げてください。",
        "source_priority": "",
    },
    1: {  # 火曜
        "theme": "経済指標・統計",
        "categories": ["経済指標", "その他"],
        "topic_guidance": "CPI、雇用統計、GDP、PMIなど主要経済指標の発表・予想・結果に関するトピックを優先的に取り上げてください。",
        "source_priority": "",
    },
    2: {  # 水曜
        "theme": "為替・債券市場",
        "categories": ["為替・債券", "その他"],
        "topic_guidance": "ドル円、ユーロドルなどの為替動向、米国債利回り、日本国債の動きに関するトピックを優先的に取り上げてください。",
        "source_priority": "",
    },
    3: {  # 木曜
        "theme": "個別企業・セクター動向",
        "categories": ["企業決算", "その他"],
        "topic_guidance": "テック企業の決算発表、セクターローテーション、注目企業の業績見通しに関するトピックを優先的に取り上げてください。",
        "source_priority": "",
    },
    4: {  # 金曜
        "theme": "税制・規制・制度変更",
        "categories": ["規制・制度", "その他"],
        "topic_guidance": "日米の税制改正、金融規制の変更、NISA制度の動向に関するトピックを優先的に取り上げてください。",
        "source_priority": "日本語ソース（日本経済新聞、東洋経済、ダイヤモンド、NHK）を優先してください。",
    },
}

# 全カテゴリ（バリデーション用）
ALL_CATEGORIES = {
    "金融政策", "経済指標", "企業決算", "為替・債券",
    "コモディティ", "日本市場", "規制・制度", "その他",
}


def get_day_theme():
    """今日のJST曜日に基づくテーマを返す."""
    jst = timezone(timedelta(hours=9))
    weekday = datetime.now(jst).weekday()  # 0=月, 4=金
    return DAY_THEMES.get(weekday)


def is_monday():
    """今日がJSTで月曜日かどうか."""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).weekday() == 0


def build_system_prompt(theme_info, previous_topics_json=None, include_calendar=False):
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
        if theme_info.get("source_priority"):
            source_section = f"""
**情報ソース優先指定**: {theme_info['source_priority']}
"""

    calendar_section = ""
    if include_calendar:
        calendar_section = """
また、今週（月〜金）の注目経済イベント・指標発表スケジュールも取得し、JSONの "weekly_calendar" キーに含めてください。
"weekly_calendar" は以下の形式の配列です：
[
  {{ "date": "3/11(火)", "event": "米CPI発表", "note": "インフレ動向の最重要指標" }}
]
5〜10件程度、市場に影響の大きいイベントを厳選してください。
"""

    calendar_json_part = ""
    if include_calendar:
        calendar_json_part = """,
  "weekly_calendar": [
    {{
      "date": "M/D(曜)",
      "event": "イベント名",
      "note": "注目ポイント（1文）"
    }}
  ]"""

    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y年%m月%d日")
    yesterday_str = (datetime.now(jst) - timedelta(days=1)).strftime("%Y年%m月%d日")

    return f"""\
あなたは金融・経済市場専門のニュース収集AIです。
**今日は{today_str}です。** {yesterday_str}〜{today_str}の最新ニュースのみを対象にしてください。
古い記事（1週間以上前のもの）は絶対に含めないでください。URLの日付も確認し、最新のものだけを選んでください。
信頼できる公式・金融メディアのみを厳選し、**以下のJSON形式のみで出力**してください。他の説明文、挨拶、Markdown、```json は一切出力しないこと。JSONが不正にならないよう厳密に守ってください。
{theme_section}
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
{source_section}{dedup_section}{calendar_section}
出力は厳密にこのJSONのみ：
{{
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "topics": [
    {{
      "title": "ニュースタイトル（日本語）",
      "category": "カテゴリ（金融政策 / 経済指標 / 企業決算 / 為替・債券 / コモディティ / 日本市場 / 規制・制度 / その他 のいずれか1つ厳密に）",
      "importance": 1〜10の整数,
      "summary": "2〜3文の正確な要約（日本語）",
      "url": "完全なソースURL",
      "insight": "投資家・市場関係者への影響と具体的なポイント（日本語、1〜2文）"
    }}
  ],
  "overall_summary": "全体の1〜2文まとめ（日本語）"{calendar_json_part}
}}"""


def build_user_prompt(theme_info, include_calendar=False):
    """曜日テーマを反映したUSER_PROMPTを構築."""
    base = "過去24時間の金融・経済ニュースTOP10を収集し、指定のJSONで出力してください。"
    if theme_info:
        base = f"今日のテーマは「{theme_info['theme']}」です。このテーマを中心に、{base}"
    if include_calendar:
        base += " また、今週の注目経済イベントも weekly_calendar に含めてください。"
    return base


def get_past_report_urls():
    """S3から直近7日分のレポートを取得し、既出URLリストを返す（変更1 第1段階）."""
    s3_bucket = os.environ.get("S3_BUCKET")
    aws_region = os.environ.get("AWS_REGION")
    if not s3_bucket or not aws_region:
        print("S3_BUCKET/AWS_REGION not set, skipping URL dedup")
        return set(), None

    try:
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client("s3", region_name=aws_region)

        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst)
        urls = set()
        previous_day_topics = None

        for days_ago in range(1, 8):
            d = today - timedelta(days=days_ago)
            key = f"reports/finance/{d.strftime('%Y-%m-%d')}.json"
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
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    continue
                print(f"Warning: failed to fetch {key}: {e}")
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


def save_weekly_calendar(report):
    """月曜の場合、weekly_calendarを別ファイルとして保存."""
    calendar = report.get("weekly_calendar", [])
    if calendar:
        with open("weekly_calendar.json", "w", encoding="utf-8") as f:
            json.dump(calendar, f, ensure_ascii=False, indent=2)
        print(f"weekly_calendar.json generated: {len(calendar)} events")
        return True
    return False


def main():
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y-%m-%d")

    # 曜日テーマ取得
    theme_info = get_day_theme()
    if theme_info:
        print(f"Today's theme: {theme_info['theme']}")
    else:
        print("No theme for today (weekend?)")

    # 月曜なら経済カレンダーも取得
    include_calendar = is_monday()
    if include_calendar:
        print("Monday: will include weekly calendar")

    # S3から過去レポート取得（重複排除用）
    past_urls, previous_day_topics = get_past_report_urls()

    # プロンプト構築
    system_prompt = build_system_prompt(theme_info, previous_day_topics, include_calendar)
    user_prompt = build_user_prompt(theme_info, include_calendar)

    print(f"Calling Grok API ({MODEL_SEARCH}) with web_search for finance report {today}...")
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_SEARCH,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "tools": [{"type": "web_search"}],
        },
        timeout=180,
    )
    if resp.status_code != 200:
        print(f"API Error {resp.status_code}: {resp.text[:500]}")
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

    # 経済カレンダーを別ファイルとして保存（月曜のみ）
    has_calendar = save_weekly_calendar(report)

    with open("finance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"finance_report.json generated: {len(report['topics'])} topics")
    if has_calendar:
        print("HAS_WEEKLY_CALENDAR=true")


if __name__ == "__main__":
    main()
