PYTHON ?= .venv/bin/python
PIP = .venv/bin/pip

.PHONY: help venv install setup run docker-run docker-build stop download profile seed validate-data analytics test test-unit lint format clean train evaluate benchmark llm-eval demo
help: ## Show commands
	@awk 'BEGIN {FS=":.*## "; print "MovieGraph commands:"} /^[a-zA-Z-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
venv: ## Create an isolated Python 3.12+ environment
	@test -d .venv || python3 -m venv .venv
install: venv ## Install pinned application and development dependencies
	$(PYTHON) -m pip install -r requirements.txt
setup: ## Create local secrets without printing or overwriting them
	$(PYTHON) -m scripts.setup
run: ## Run API on the host (Neo4j must already be running)
	$(PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port 18081
docker-build: ## Build the API image
	docker compose build
docker-run: setup ## Start the three services
	docker compose up -d --build --wait --wait-timeout 300
stop: ## Stop services without deleting data
	docker compose down
download: ## Download and checksum MovieLens small
	$(PYTHON) -m scripts.data download
profile: ## Validate source data and generate a quality report
	$(PYTHON) -m scripts.data profile
seed: ## Idempotently create schema and import the dataset
	$(PYTHON) -m scripts.data seed
validate-data: ## Check graph invariants and expected source counts
	$(PYTHON) -m scripts.data validate
analytics: ## Build versioned GDS similarity, Louvain and PageRank
	$(PYTHON) -m app.analytics.build
test: ## Run unit/API/real Neo4j tests with coverage (requires seeded DB)
	$(PYTHON) -m scripts.check_database
	$(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-report=html
test-unit: ## Run isolated tests without requiring Neo4j
	$(PYTHON) -m pytest tests/unit tests/api
lint: ## Enforce teacher rules and a pylint score of at least 9.5
	$(PYTHON) -m pylint --rcfile=.pylintrc --fail-under=9.5 app scripts
format: ## Format Python code consistently
	$(PYTHON) -m black app scripts tests
train: ## Train and evaluate the frozen-history ML experiment
	$(PYTHON) -m app.ml.experiment
evaluate: train ## Alias for the reproducible ML experiment
benchmark: ## Capture actual PROFILE plans and before/after latency
	$(PYTHON) -m scripts.benchmark
llm-eval: ## Run the 40-case local model/guardrail evaluation
	$(PYTHON) -m scripts.evaluate_llm
demo: ## Run container health/API smoke checks
	$(PYTHON) -m scripts.smoke
clean: ## Remove Python caches only, preserving datasets and volumes
	$(PYTHON) -m scripts.clean
