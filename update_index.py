"""S3からindex.jsonを取得し、新しいレポートエントリを追加して保存する."""
import json
import os
import sys


def main():
    date = os.environ["REPORT_DATE"]
    report_path = sys.argv[1] if len(sys.argv) > 1 else "report.json"
    index_path = "index.json"

    # Load the generated report
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Load existing index (may not exist)
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"reports": []}

    # Remove duplicate if same date exists
    index["reports"] = [r for r in index["reports"] if r["date"] != date]

    # Insert new entry
    index["reports"].insert(0, {
        "date": date,
        "topic_count": len(report.get("topics", [])),
        "overall_summary": report.get("overall_summary", ""),
        "file": f"{date}.json",
    })

    # Sort descending by date
    index["reports"].sort(key=lambda r: r["date"], reverse=True)

    # Save
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"index.json updated: {len(index['reports'])} reports")


if __name__ == "__main__":
    main()
