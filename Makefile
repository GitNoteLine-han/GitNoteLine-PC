.PHONY: run-web install

# ── Development ─────────────────────────────────────────────────────

run-web:          ## Start Flask dev server (random port, production mode)
	python -m web

run-web-debug:    ## Start Flask dev server with debug/reloader
	python -m web --debug

run-web-port:     ## Start with a specific port, e.g. make run-web-port PORT=8080
	python -m web --port $(PORT)

# ── Setup ───────────────────────────────────────────────────────────

install:          ## Install Python dependencies
	pip install -r requirements.txt