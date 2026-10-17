#!/usr/bin/env python3
"""Check generated routes, assets, anchors, SEO, and translation links offline.

Inspired by Vonng/vonng.com's generated-route validation approach; this
implementation checks rendered HTML and supports deployment under a subpath.
"""

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = set()
        self.links = []
        self.anchors = []
        self.alternates = {}
        self.canonical = None
        self.language = None
        self.card_images = []
        self.active_card = None
        self.card_columns = []
        self.blog_default = None
        self.has_share_bar = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if "data-td-share" in attrs:
            self.has_share_bar = True
        if tag == "article" and "td-blog-card" in classes:
            self.card_images.append([])
            self.active_card = len(self.card_images) - 1
        if tag == "img" and "td-blog-card__image" in classes and self.active_card is not None:
            self.card_images[self.active_card].append(attrs.get("src", ""))
        if "td-blog-cards" in classes:
            self.card_columns.append(attrs.get("style", ""))
        if "data-td-blog-default" in attrs:
            self.blog_default = attrs["data-td-blog-default"]
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "link" and attrs.get("hreflang"):
            self.alternates[attrs["hreflang"]] = attrs.get("href")
        if tag == "a" and attrs.get("href"):
            self.anchors.append(attrs["href"])
        if tag == "meta" and (attrs.get("property") == "og:image" or attrs.get("name") == "twitter:image"):
            self.links.append(attrs["content"])
        if attrs.get("style"):
            self.links.extend(re.findall(r"url\(['\"]?([^)'\"]+)", attrs["style"]))
        for key in ("href", "src", "poster"):
            if attrs.get(key):
                self.links.append(attrs[key])
        if attrs.get("srcset"):
            self.links.extend(part.strip().split()[0] for part in attrs["srcset"].split(",") if part.strip())
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"url=(.+)", attrs.get("content", ""), re.I)
            if match:
                self.links.append(match[1])

    def handle_endtag(self, tag):
        if tag == "article":
            self.active_card = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", default="public")
    parser.add_argument("--base-url", default="https://blog.donnyguo.com/")
    args = parser.parse_args()
    root = Path(args.public_dir).resolve()
    base = args.base_url.rstrip("/") + "/"
    origin = urlsplit(base)
    prefix = origin.path
    docs = {p: Document(p.read_text()) for p in root.rglob("*.html")}
    errors = set()

    def resolve(url, source):
        target = urlsplit(urljoin(source, url))
        if target.scheme not in ("http", "https"):
            return None
        if target.hostname in ("localhost", "127.0.0.1") and target.netloc != origin.netloc:
            errors.add(f"{source}: preview URL leaked into production: {url}")
        if target.netloc != origin.netloc:
            return None
        path = unquote(target.path)
        if not path.startswith(prefix):
            errors.add(f"{source}: link escapes deployment prefix: {url}")
            return None
        file = (root / path[len(prefix):]).resolve()
        if not file.is_relative_to(root):
            errors.add(f"{source}: path escapes output directory: {url}")
            return None
        if file.is_dir():
            file /= "index.html"
        if not file.is_file():
            errors.add(f"{source}: missing target {url}")
            return None
        return file, unquote(target.fragment)

    if not docs:
        errors.add("No generated HTML found; build the site first")
    for file, doc in docs.items():
        relative = file.relative_to(root).as_posix()
        source = urljoin(base, relative.removesuffix("index.html"))
        if doc.has_share_bar:
            errors.add(f"{relative}: page-end sharing must remain disabled")
        if any(len(images) != 1 or not images[0] for images in doc.card_images):
            errors.add(f"{relative}: every article card must have one thumbnail")
        for link in doc.links:
            resolved = resolve(link, source)
            if resolved:
                target, fragment = resolved
                if fragment and target in docs and fragment not in docs[target].ids:
                    errors.add(f"{relative}: missing anchor {link}")

    for route in ("index.html", "en/index.html", "blog/index.html", "en/blog/index.html"):
        doc = docs.get(root / route)
        if not doc:
            continue
        if not doc.card_images:
            errors.add(f"{route}: missing cover-card article layout")
        if not any(re.search(r"--td-card-columns:\s*3\s*(?:;|$)", style) for style in doc.card_columns):
            errors.add(f"{route}: article cards must use three columns")
        if doc.blog_default is not None and doc.blog_default != "cards":
            errors.add(f"{route}: default article layout must be cards")

    for page in Path("content").rglob("*.md"):
        stem, language, _ = page.name.rsplit(".", 2)
        segments = list(page.relative_to("content").parent.parts)
        if stem not in ("index", "_index"):
            segments.append(stem)
        route = "/".join((["en"] if language == "en" else []) + segments)
        file = root / route / "index.html"
        doc = docs.get(file)
        if not doc:
            errors.add(f"{page}: page was not published at {route}/")
            continue
        expected = urljoin(base, route + "/" if route else "")
        if doc.canonical != expected:
            errors.add(f"{page}: incorrect canonical URL {doc.canonical}")
        if not doc.language or not doc.language.startswith(language):
            errors.add(f"{page}: incorrect HTML language {doc.language}")
        peer_language = "zh" if language == "en" else "en"
        peer_route = "/".join((["en"] if peer_language == "en" else []) + segments)
        peer_url = urljoin(base, peer_route + "/" if peer_route else "")
        if peer_url not in doc.alternates.values():
            errors.add(f"{page}: missing translation alternate {peer_url}")
        if not any(urljoin(expected, link) == peer_url for link in doc.anchors):
            errors.add(f"{page}: missing visible language-switch link")

    for language_root in (root, root / "en"):
        for name in ("index.xml", "blog/index.xml", "llms.txt", "sitemap.xml"):
            if not (language_root / name).is_file():
                errors.add(f"Missing publication output: {language_root / name}")
    cover_sizing_found = False
    for file in root.rglob("*.css"):
        source = urljoin(base, file.relative_to(root).as_posix())
        css = file.read_text()
        for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if ".td-blog-card__image" not in (item.strip() for item in selectors.split(",")):
                continue
            properties = {}
            for declaration in declarations.split(";"):
                if ":" in declaration:
                    name, value = declaration.split(":", 1)
                    properties[name.strip()] = re.sub(r"\s+", "", value)
            if (properties.get("width") == "100%" and properties.get("height") == "auto"
                    and properties.get("aspect-ratio") == "16/9"):
                cover_sizing_found = True
        for url in re.findall(r"url\(['\"]?([^)'\"]+)", css):
            resolve(url, source)
    if not cover_sizing_found:
        errors.add("Missing shared 16:9 cover sizing with width:100% and height:auto")
    indexes = list(root.rglob("*offline-search-index*.json"))
    if len(indexes) < 2:
        errors.add("Missing bilingual search indexes")
    for file in indexes:
        entries = json.loads(file.read_text())
        for entry in entries:
            resolve(entry["ref"], base)
        if not entries:
            errors.add(f"Empty search index: {file}")

    for error in sorted(errors):
        print(error)
    if errors:
        raise SystemExit(1)
    print(f"Site checks passed: {len(docs)} HTML pages, bilingual routes, assets, anchors, and search indexes.")


if __name__ == "__main__":
    main()
