# Blog conventions

- Use English for code, comments, README, and commit messages.
- Put each article in `content/blog/<slug>/` with `index.en.md` and `index.zh.md`.
- Set `title`, `date`, `description`, `authors`, `categories`, `tags`, and `images`
  in both editions. Choose appropriate categories and tags when preparing an
  article. Both editions must select the same local thumbnail.
- Keep thumbnails and all article images beside the Markdown files; use relative
  filenames. Retain source attribution and licenses for downloaded images.
- Use H2/H3 sections and linked footnotes. Suggest tables and diagrams where
  they clarify the article; preserve the author's meaning and dated data.
- Keep three-column cover cards, 16:9 image frames, and page-end sharing disabled.
- Treat `make check` and the installed pre-commit hook as required gates.
  CI must enforce the same rules; warnings alone must not fail builds.
- Do not commit, push, or add unrelated UI features unless requested.
