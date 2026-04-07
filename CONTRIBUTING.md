# Contributing

Welcome. This guide covers the development workflow, code conventions, and how changes reach production.

For *operational* deploy details (URLs, AWS resources, data refresh, on-call recipes) see [DEPLOY.md](./DEPLOY.md).

---

## TL;DR

```bash
git checkout -b feature/your-change
# ...code, test, commit...
git push -u origin feature/your-change
gh pr create --base main
# ...get PR reviewed and merged...
# CI auto-deploys to dev. Smoke-test the dev URL, then approve prod from Actions UI.
```

---

## Local setup

Requires Python 3.11+ and Node 22+.

```bash
pip install -e ".[dev,web]"      # Python deps
cd web && npm ci && cd ..        # Frontend deps

make test                        # Pytest with 85% coverage gate
make lint                        # ruff
make typecheck                   # mypy strict mode

./start.sh                       # Backend :8000 + Vite :5173
```

The data pipeline is independent of the API:

```bash
make pipeline                    # Full pipeline: ingest → clean → enrich → score
make audit                       # Coverage and column stats
```

---

## Branching model

**Trunk-based.** One long-lived branch: `main`. Everything else is a short-lived feature/fix branch off main.

- `feature/<short-name>` for new functionality
- `fix/<short-name>` for bug fixes
- `docs/<short-name>` for documentation-only changes
- `chore/<short-name>` for tooling, deps, refactors

Direct commits to `main` are blocked by a pre-commit hook. Always go via PR.

---

## Pull requests

Every change ships through a PR against `main`. Before opening one:

1. **Run the local checks:** `make test && make lint && make typecheck`
2. **Smoke-test in `./start.sh`** if your change touches code paths that run at request time
3. **Keep the PR scoped.** One logical change per PR is much easier to review and revert

PR title should describe the change in the imperative ("Add X", "Fix Y", "Refactor Z"). The body should explain *why*, not what — the diff already shows the what.

---

## CI/CD pipeline

Every push to `main` triggers `.github/workflows/deploy.yml`, which has three jobs:

```
build  →  deploy-dev  →  [approval gate]  →  deploy-prod
```

### `build`
- Authenticates to AWS via OIDC (no static keys)
- Syncs `data/processed/` from S3 (`asteroid-cost-atlas-data-<account>`)
- Builds the multi-stage Docker image (frontend → Vite bundle → mounted into Python image)
- Pushes two tags to ECR: `:sha-<short>` (immutable record) and `:dev` (moving alias)

### `deploy-dev`
- Runs automatically after `build`
- Calls `apprunner start-deployment` on `asteroid-cost-atlas-dev`
- Dev pulls the new `:dev` image and rolls out (~2 min)

### `deploy-prod`
- **Paused** by GitHub `environment: production` until a required reviewer approves
- **Only the repository owner (`Ron-Zehavi`) is configured as a required reviewer.** Other contributors cannot approve a production deploy. If you need a prod ship, get your PR merged and ping the owner
- After approval: retags the build's `:sha-<short>` as `:prod` in ECR (the *exact same image bytes* that ran in dev)
- Calls `apprunner start-deployment` on `asteroid-cost-atlas-prod`
- Prod pulls the new `:prod` image and rolls out

The promotion rule is **promote the artifact, not the build**: prod runs the identical image dev validated. Nothing is rebuilt between environments.

---

## How to ship a change end-to-end

1. **Open and merge a PR to `main`** (see [Pull requests](#pull-requests))
2. **Wait for CI** — the `build` and `deploy-dev` jobs run automatically (~5 min total). Watch in the Actions tab
3. **Smoke-test dev** at the dev URL (see [DEPLOY.md](./DEPLOY.md)). Click around, check anything your change touched
4. **Approve prod** (repo owner only) when ready:
   - Open the workflow run page in the Actions tab
   - Click **"Review deployments"** in the yellow banner
   - Check `production` and click **"Approve and deploy"**
   - Other contributors should ping the repo owner once their PR is merged and dev is verified
5. **Verify prod** at the prod URL

If dev looks broken, **don't approve prod**. Push a fix. The waiting prod job will be superseded by the new run. Prod stays on the previous version the whole time.

---

## Code conventions

- Strict mypy (`strict = true`), line length 100, ruff rules: E/F/I/UP
- All Python modules use `from __future__ import annotations`
- Pydantic models use `ConfigDict(extra="forbid")`
- Scalar functions return `float("nan")` for invalid input rather than raising
- Structured JSON logging with per-run metadata files in `data/raw/metadata/`
- Date-stamped output files (e.g. `sbdb_clean_20260330.parquet`)
- Frontend: TypeScript strict mode, no unused imports (CI fails on `noUnusedLocals`)

---

## Tests

- **Pytest** with an 85 % coverage gate (`make test`)
- Tests live under `tests/`, mirroring the `src/` package structure
- New code must include unit tests. Coverage drops below 85 % will fail CI
- **Bug fixes must include a functional test for the corrected behavior.** Don't just assert "the original symptom no longer happens" — assert that the function or endpoint produces the *correct* output for the class of input the bug exposed. The difference matters: wrapping the symptom in `try/except` would pass a symptom-only test but a functional test would still fail because the underlying behavior is still wrong. The test should fail on `main` before your fix and pass after. Include a one-line comment pointing at the original failure mode

Frontend tests (Vitest) are wired but minimal — feel free to add coverage for non-trivial UI logic.

---

## Infrastructure changes

Terraform lives under `infra/` (shared resources + dev) and `infra/prod/` (prod-only, separate state).

Infrastructure is **not** applied by CI — it's applied manually from a maintainer's laptop with the `asteroid` AWS profile:

```bash
cd infra && AWS_PROFILE=asteroid terraform plan
AWS_PROFILE=asteroid terraform apply
```

Infrastructure changes go through the same PR flow as code. Mention any non-obvious blast radius in the PR description.

---

## Things that are easy to get wrong

- **`data/processed/**` is gitignored** — don't try to commit parquet files. Data is hydrated from S3 in CI before the docker build
- **Don't push images from your laptop** — home upload bandwidth is too slow; let CI do it
- **Don't bypass hooks** with `--no-verify`. If a pre-commit hook fails, fix the underlying issue
- **Don't add Co-Authored-By or AI attribution** in commits or PRs
- **`README.md` must be in the image** (hatchling needs it). It's already in the Dockerfile — don't remove it
- **App Runner instance must be ≥ 1 vCPU / 2 GB**. Smaller sizes OOM loading the parquet
- **Path resolution** in code that needs to find `data/processed/` or `web/dist/` must work both in dev (where `pyproject.toml` is at the repo root) and in the installed-package layout inside the container. See `api/deps.py` and `api/app.py` for the env-var override pattern
- **Pre-commit hook blocks direct commits to `main`** — always go via PR
