HUGO ?= hugo
PORT ?= 18743
BASE_URL ?= https://blog.donnyguo.com/

# Always use the release pinned in go.mod, including for local previews.
export GOWORK := off
export HUGO_MODULE_WORKSPACE := off
PINNED_HUGO = env -u HUGO_MODULE_REPLACEMENTS $(HUGO)

.PHONY: dev build check
dev:
	$(PINNED_HUGO) server --bind 127.0.0.1 --port $(PORT) --buildDrafts

build:
	$(PINNED_HUGO) --gc --minify --cleanDestinationDir --environment production --baseURL "$(BASE_URL)"

check:
	python3 bin/check-content.py
	$(PINNED_HUGO) --gc --minify --cleanDestinationDir --environment production --baseURL "$(BASE_URL)" --printPathWarnings --panicOnWarning
	python3 bin/check-site.py --base-url "$(BASE_URL)"
