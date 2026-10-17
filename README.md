# Donny's Blog

Dongping Guo's notes on open source, self-hosting, and security.
Built with [Hugo](https://gohugo.io/) and [OINK](https://github.com/pgsty/oink).

- Chinese: https://blog.donnyguo.com/
- English: https://blog.donnyguo.com/en/

## Build

Requires **Hugo Extended 0.166.0+**, **Go 1.27+**, and **Python 3.11+**.

```sh
make dev     # Preview at localhost:18743
make build   # Production site in public/
make check   # Content, build, links, assets, and language pairs
make hooks   # Install the local pre-commit hook
```

Run `make hooks` once per clone. Commits then check staged whitespace and run
`make check` against the working tree; failures block the commit.
Build warnings remain visible; actual build errors and failed checks block
the commit.

OINK is pinned in `go.mod`. Upgrade with
`hugo mod get github.com/pgsty/oink@vX.Y.Z && hugo mod tidy`.

## Publish

Enable GitHub Pages with **GitHub Actions** as its source. The Pages workflow
deploys pushes to `main`; pull requests run checks only. Set the Pages custom
domain to `blog.donnyguo.com` and configure its DNS before using that address.
Set the repository Actions variable `SITE_URL` to `https://blog.donnyguo.com/`
under **Settings → Secrets and variables → Actions → Variables**. This takes
priority over the Pages-reported URL, avoiding stale repository paths during
custom-domain setup. Without `SITE_URL`, the workflow uses the Pages URL.

For other static hosts, use `make build BASE_URL=https://your-domain/` and
publish `public/` with the same Hugo and Go versions.

## Layout

```text
hugo.yaml               # Site settings and localized menus
content/                # Paired index.en.md and index.zh.md pages
content/blog/<post>/     # Article text and its shared images in one page bundle
data/home/              # Localized home page copy
data/footer/            # Localized footer links
assets/                 # Site branding and styles
layouts/                # Small additions to the theme
static/images/          # Shared site images, such as the avatar
bin/                    # Content and generated-site checks
```

The structure and build workflow are inspired by
[Vonng's blog](https://github.com/Vonng/vonng.com) (CC BY 4.0); the checks here
are written for this site's bilingual routes.

Original articles and profile content are copyright Dongping Guo and licensed
under [CC BY 4.0](LICENSE). Third-party assets retain their respective licenses;
OINK is Apache-2.0 licensed.
