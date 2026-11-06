"""Render a frozen synthetic fixture; no solver invocation or implicit output path."""
import argparse
import base64
import json
from pathlib import Path
from app.services.saved_report import render_saved_report


def main():
    parser = argparse.ArgumentParser(description="Render the frozen synthetic report fixture")
    parser.add_argument("--output-dir", required=True, help="existing directory to receive a new report")
    parser.add_argument("--locale", choices=("en", "zh-CN"), default="en")
    parser.add_argument("--include-survival", action="store_true",
                        help="also display frozen Kaplan-Meier and experimental zero-failure results")
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("output-dir must be an existing directory")
    fixture = Path(__file__).with_name("saved_results.json")
    records = json.loads(fixture.read_text(encoding="utf-8"))
    if args.include_survival:
        survival_fixture = Path(__file__).with_name("saved_survival_results.json")
        records.extend(json.loads(survival_fixture.read_text(encoding="utf-8")))
    report = render_saved_report(records, locale=args.locale)
    target = directory / "reliability-report.html"
    with target.open("xb") as stream:
        stream.write(base64.b64decode(report["content_base64"], validate=True))
    print("Created", target)
    print("SHA256", report["sha256"])


if __name__ == "__main__":
    main()
