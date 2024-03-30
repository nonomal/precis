.PHONY: tw
tw:
	npx tailwindcss -i ./rssynthesis/templates/input.css -o ./rssynthesis/static/output.css --watch

.PHONY: install
install:
	npm install -D tailwindcss @tailwindcss/typography daisyui@latest
	pip install -e .

.PHONY: run
run:
	uvicorn rssynthesis.rssynthesis:app