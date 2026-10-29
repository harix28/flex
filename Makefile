PYTHON ?= python
SUBSET ?= FD001
OUT ?= runs/$(SUBSET)-new
.PHONY: test download train deploy deploy-dev down logs build

test:
	$(PYTHON) -m pytest -q

download:
	$(PYTHON) -m sentinel.download --out data/raw

train:
	$(PYTHON) -m sentinel.train --data-dir data/raw --subset $(SUBSET) --out $(OUT)

deploy:
	bash scripts/deploy.sh --rebuild

deploy-dev:
	bash scripts/deploy.sh --dev --rebuild

down:
	bash scripts/deploy.sh --down

logs:
	docker compose --env-file .env.production logs -f

build:
	docker compose --env-file .env.production build
