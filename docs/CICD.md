# CI/CD Pipeline

This document describes the development workflow, continuous integration, and continuous deployment process for Asteroid Cost Atlas.

---

## Overview

```
feature branch (commit often)
       │
       ▼
  make ship ─── lint ─── mypy ─── pytest ─── vitest
       │                                        │
       │              all pass?                 │
       │          no ──► fix & retry            │
       │          yes ──────────────────────────┘
       ▼
  push branch + open PR to main
       │
       ▼
  GitHub Actions CI (Python 3.11 + 3.12 matrix)
       │  ├── ruff check
       │  ├── mypy --strict
       │  ├── pytest + coverage
       │  └── pip-audit
       │
       ▼
  code review + merge PR
       │
       ▼
  GitHub Actions CD (on push to main)
       ├── Docker build (multi-stage: Node frontend + Python backend)
       ├── Push image to Amazon ECR
       └── Deploy to ECS (rolling update, wait for stable)
```

---

## Development Workflow

### 1. Create a feature branch

```bash
git checkout -b feature/my-change
```

### 2. Develop and commit

Work normally, committing small, meaningful changes as you go.

```bash
git add src/asteroid_cost_atlas/scoring/orbital.py
git commit -m "Improve delta-v proxy for high-inclination orbits"
```

### 3. Ship when ready

```bash
make ship                          # auto-generates PR title from branch name
make ship TITLE="Add NIR scoring"  # custom PR title
```

`make ship` runs these steps in order:

1. **Pre-flight** — verifies you're not on `main`, all changes are committed, and `gh` CLI is installed
2. **Lint** — `ruff check src tests`
3. **Type-check** — `mypy src` (strict mode)
4. **Python tests** — `pytest` with 85% coverage gate
5. **Frontend tests** — `cd web && npm test -- --run` (vitest)
6. **Push** — `git push -u origin <branch>`
7. **PR** — opens a pull request to `main` via `gh pr create` (or reports existing PR)

If any gate fails, the script stops immediately. Fix the issue and re-run.

---

## Continuous Integration (CI)

Defined in `.github/workflows/ci.yml`. Triggers on:
- Every push to `main`
- Every pull request (any branch)

### CI matrix

| Check | Python 3.11 | Python 3.12 |
|---|---|---|
| `pip install -e ".[dev]"` | x | x |
| `pip install --no-deps .` (build verify) | x | x |
| `ruff check src tests` | x | x |
| `mypy src` | x | x |
| `pytest --junitxml` | x | x |
| `pip-audit --strict` | x | x |

### Artifacts

Each CI run uploads:
- `test-results-{version}.xml` — JUnit XML for PR status checks
- `htmlcov/` — HTML coverage report

### Dependency audit

`pip-audit` runs with `continue-on-error: true` — it won't block merges, but vulnerabilities appear in the Actions log for review.

---

## Continuous Deployment (CD)

The `deploy` job runs **only** on push to `main` (i.e., after a PR is merged). It requires the `ci` job to pass first.

### Deploy steps

1. **Authenticate** — OIDC-based AWS authentication (no long-lived access keys)
2. **ECR login** — authenticate Docker to Amazon ECR
3. **Build & push** — multi-stage Docker build, tagged with both `latest` and the commit SHA
4. **ECS deploy** — force new deployment on the ECS service, then wait for stability

### Docker image

The Dockerfile produces a single container that serves both the API and frontend:

```
Stage 1 (node:22-slim)  → npm ci && npm run build → frontend dist/
Stage 2 (python:3.12-slim) → pip install .[web] + copy frontend → uvicorn on :8000
```

---

## AWS Setup

### Prerequisites

- An ECR repository for the Docker image
- An ECS cluster with a service running the container
- An IAM role with OIDC trust for GitHub Actions

### GitHub Secrets

Configure these in your repository settings (Settings > Secrets and variables > Actions):

| Secret | Description | Example |
|---|---|---|
| `AWS_ROLE_ARN` | IAM role ARN for OIDC auth | `arn:aws:iam::123456789012:role/github-actions-deploy` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `ECR_REPOSITORY` | ECR repository name | `asteroid-cost-atlas` |
| `ECS_CLUSTER` | ECS cluster name | `prod-cluster` |
| `ECS_SERVICE` | ECS service name | `asteroid-cost-atlas-svc` |

### GitHub Environment

Create a `production` environment in Settings > Environments. Optional but recommended protections:

- **Required reviewers** — require approval before deploy (useful for team workflows)
- **Wait timer** — add a delay before deploy starts (e.g., 5 minutes to catch mistakes)
- **Branch protection** — restrict to `main` only

### IAM Role Trust Policy

The deploy role needs an OIDC trust policy for GitHub Actions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/asteroid-cost-atlas:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### IAM Role Permissions

The role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices"
      ],
      "Resource": "arn:aws:ecs:*:*:service/prod-cluster/asteroid-cost-atlas-svc"
    }
  ]
}
```

---

## Troubleshooting

### `make ship` fails at lint/type-check

Fix the issues locally. Run `make format` to auto-fix formatting, then `make lint` and `make typecheck` to verify.

### `make ship` says "uncommitted changes"

Commit or stash your work first. The ship script requires a clean working tree to ensure what you test locally matches what gets pushed.

### CI passes but deploy fails

Check the Actions log for the deploy job. Common issues:
- **Missing secrets** — verify all 5 secrets are configured in GitHub
- **IAM permissions** — the role may lack ECR or ECS permissions
- **ECS service not found** — verify cluster and service names match

### PR already exists

If a PR already exists for your branch, `make ship` will skip PR creation and print the existing PR URL. Push new commits and they'll be picked up by the existing PR.

---

## Quick Reference

| Command | What it does |
|---|---|
| `make ship` | Full local gate + push + open PR |
| `make test` | Python tests only |
| `make web-test` | Frontend tests only |
| `make test-all` | Python + frontend tests |
| `make lint` | Lint check |
| `make typecheck` | mypy strict |
| `make docker` | Build Docker image locally |
| `make docker-run` | Run container locally on :8000 |
