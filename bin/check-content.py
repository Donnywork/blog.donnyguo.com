#!/usr/bin/env python3
"""Validate bilingual article metadata and images stored in page bundles."""

import argparse
import re
import shlex
from pathlib import Path
from urllib.parse import unquote, urlsplit


IMAGE_SUFFIXES = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


def prose_only(body):
    """Exclude fenced examples before checking article formatting and links."""
    prose = []
    fence = None
    for line in body.splitlines():
        if fence:
            if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*", line):
                fence = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if opening:
            fence = opening[1]
        else:
            prose.append(line)
    return "\n".join(prose)


def metadata_list(header, key):
    """Read the simple YAML flow/block lists used for article metadata."""
    lines = header.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}:[ \t]*(.*)$", line)
        if not match:
            continue
        value = match[1].strip()
        flow = re.fullmatch(r"\[(.*)\]\s*(?:#.*)?", value)
        if flow:
            lexer = shlex.shlex(flow[1], posix=True)
            lexer.whitespace = ","
            lexer.whitespace_split = True
            try:
                return [item.strip() for item in lexer if item.strip()]
            except ValueError:
                return []
        if value and not value.startswith("#"):
            return []
        items = []
        for item in lines[index + 1:]:
            if not item.strip() or item.lstrip().startswith("#"):
                continue
            match = re.match(r"^[ \t]*-[ \t]+(.+)$", item)
            if not match:
                break
            try:
                items.append(" ".join(shlex.split(match[1], comments=True)))
            except ValueError:
                return []
        return items
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = []
    content = Path("content")
    pages = sorted(content.rglob("*.md"))
    covers = {}

    def check_image(page, reference):
        url = urlsplit(reference)
        name = Path(unquote(url.path))
        if (url.scheme or url.netloc or url.query or url.fragment
                or name.is_absolute() or len(name.parts) != 1 or "\\" in reference):
            errors.append(f"{page}: image must be in the article directory: {reference}")
            return
        image = page.parent / name
        if image.suffix.lower() not in IMAGE_SUFFIXES:
            errors.append(f"{page}: unsupported image type: {reference}")
        if not (image.is_file() and not image.is_symlink() and image.stat().st_size > 0):
            errors.append(f"{page}: missing or empty local image: {reference}")

    if not pages:
        errors.append("No content pages found")
    for page in pages:
        match = re.fullmatch(r"(.+)\.(en|zh)\.md", page.name)
        if not match:
            errors.append(f"{page}: use an .en.md or .zh.md language suffix")
            continue
        stem, language = match.groups()
        peer = page.with_name(f"{stem}.{'zh' if language == 'en' else 'en'}.md")
        if not peer.is_file():
            errors.append(f"{page}: missing translation {peer}")
        text = page.read_text()
        parts = text.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            errors.append(f"{page}: missing YAML front matter")
            continue
        header, body = parts[1:]
        required = ["title"]
        article = page.is_relative_to(content / "blog") and stem != "_index"
        if article:
            prose = prose_only(body)
            if stem != "index" or page.parent == content / "blog":
                errors.append(f"{page}: use content/blog/<slug>/index.{language}.md page bundles")
            required += ["date", "description"]
            if not body.strip():
                errors.append(f"{page}: empty article")
            for key in ("authors", "categories", "tags"):
                if not metadata_list(header, key):
                    errors.append(f"{page}: missing non-empty {key} list")
            images = metadata_list(header, "images")
            if not images:
                errors.append(f"{page}: set images: [thumbnail.webp] to a local thumbnail")
            else:
                covers[page] = images[0]
                for image in images:
                    check_image(page, image)
            for image in re.findall(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))", prose):
                check_image(page, image[0] or image[1])
            definitions = re.findall(r"^\[\^([^\]]+)\]:", prose, re.M)
            references = set(re.findall(r"\[\^([^\]]+)\](?!:)", prose))
            if len(definitions) != len(set(definitions)):
                errors.append(f"{page}: duplicate footnote definitions")
            for reference in sorted(references - set(definitions)):
                errors.append(f"{page}: missing footnote definition: {reference}")
        for field in required:
            if not re.search(rf"^{field}:\s*\S", header, re.M):
                errors.append(f"{page}: missing {field}")

    for page, cover in covers.items():
        language = page.name.rsplit(".", 2)[1]
        peer = page.with_name(f"index.{'zh' if language == 'en' else 'en'}.md")
        if peer in covers and covers[peer] != cover:
            errors.append(f"{page}: language editions must share the same thumbnail as {peer}")

    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print(f"Content checks passed: {len(pages)} pages with language peers.")


if __name__ == "__main__":
    main()
