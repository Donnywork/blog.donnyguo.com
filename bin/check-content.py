#!/usr/bin/env python3
"""Validate bilingual content; optionally verify the original migration bodies."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-migration", action="store_true")
    args = parser.parse_args()
    errors = []
    pages = sorted(Path("content").rglob("*.md"))
    if not pages:
        errors.append("No content pages found")
    for page in pages:
        match = re.fullmatch(r"(.+)\.(en|zh)\.md", page.name)
        if not match:
            errors.append(f"{page}: use an .en.md or .zh.md language suffix")
            continue
        stem, language = match.groups()
        peer = page.with_name(f"{stem}.{'zh' if language == 'en' else 'en'}.md")
        if not peer.exists():
            errors.append(f"{page}: missing translation {peer}")
        text = page.read_text()
        parts = text.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            errors.append(f"{page}: missing YAML front matter")
            continue
        header, body = parts[1:]
        required = ["title"]
        if "blog" in page.parts and stem == "index":
            required += ["date", "description"]
            if not body.strip():
                errors.append(f"{page}: empty article")
        for field in required:
            if not re.search(rf"^{field}:\s*\S", header, re.M):
                errors.append(f"{page}: missing {field}")
        if "leetcode" in str(page).lower():
            errors.append(f"{page}: excluded legacy article")
        if "```Links" in body:
            errors.append(f"{page}: unconverted legacy link component")

    if args.verify_migration:
        manifest = json.loads(Path("data/migration.json").read_text())
        for article in manifest["articles"]:
            page = Path(article["destination"])
            body = page.read_text().split("---", 2)[2]
            if hashlib.sha256(body.encode()).hexdigest() != article["body_sha256"]:
                errors.append(f"{page}: differs from the recorded original body")
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print(f"Content checks passed: {len(pages)} pages with language peers.")


if __name__ == "__main__":
    main()
