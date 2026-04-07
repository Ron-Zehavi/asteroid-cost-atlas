# Deploy

Two App Runner environments. CI builds once, deploys to dev automatically, then waits for your one-click approval before promoting to prod.

| Env | Service | Pulls tag | URL |
|---|---|---|---|
| dev | `asteroid-cost-atlas-dev` | `:dev` | _set after first apply_ |
| prod | `asteroid-cost-atlas-prod` | `:prod` | _set after first apply_ |

## Daily flow

```bash
# 1. Develop
git checkout -b feature/whatever
# ...edit code...
make test && make lint && make typecheck
./start.sh                          # smoke test locally

# 2. Ship to dev
git push -u origin feature/whatever
gh pr create --base main
# ...merge PR on GitHub UI...
# CI: builds image → pushes :sha-xxx + :dev → deploys to dev (~5 min)

# 3. Smoke-test dev
curl https://<dev-url>/api/health
# poke around the live dev URL

# 4. Promote to prod
# Go to repo → Actions → click the running workflow → "Review deployments"
# → check "production" → Approve and deploy
# CI: retags :sha-xxx as :prod → deploys to prod (~5 min)
```

## Refresh data

The container bakes the parquet from S3 at build time. To update:

```bash
make pipeline                       # generates new atlas_<date>.parquet locally
aws s3 sync data/processed/ s3://asteroid-cost-atlas-data-975050282139/processed/ \
  --profile asteroid --exclude "*" --include "atlas_*.parquet"

# Trigger a CI rebuild
git commit --allow-empty -m "Refresh data" && git push
```

## Resources

| Resource | Name |
|---|---|
| AWS profile | `asteroid` (us-east-1) |
| Dev App Runner | `asteroid-cost-atlas-dev` (1 vCPU / 2 GB) |
| Prod App Runner | `asteroid-cost-atlas-prod` (1 vCPU / 2 GB) |
| ECR repo | `975050282139.dkr.ecr.us-east-1.amazonaws.com/asteroid-cost-atlas` |
| Image tags | `:dev`, `:prod` (moving aliases), `:sha-<short>` (immutable per build) |
| S3 data bucket | `asteroid-cost-atlas-data-975050282139` |
| GitHub Actions IAM role | `asteroid-cost-atlas-github-actions` (OIDC, `refs/heads/main` only) |
| Dev logs | `/aws/apprunner/asteroid-cost-atlas-dev/<id>/application` |
| Prod logs | `/aws/apprunner/asteroid-cost-atlas-prod/<id>/application` |

## Logs

```bash
SVC=$(aws apprunner list-services --region us-east-1 --profile asteroid \
  --query "ServiceSummaryList[?ServiceName=='asteroid-cost-atlas-dev'].ServiceArn | [0]" --output text)
LOG="/aws/apprunner/asteroid-cost-atlas-dev/$(echo $SVC | awk -F/ '{print $NF}')/application"
aws logs tail "$LOG" --region us-east-1 --profile asteroid --follow
# swap "dev" → "prod" for prod logs
```

## Infra changes

Terraform is split:

- `infra/` — shared resources (ECR, S3, IAM, OIDC) + dev App Runner
- `infra/prod/` — prod App Runner only (separate state, uses data sources to look up shared resources)

```bash
cd infra && AWS_PROFILE=asteroid terraform apply         # dev + shared
cd infra/prod && AWS_PROFILE=asteroid terraform apply    # prod
```

CI does **not** run terraform — only image build/push/deploy.

## GitHub environments

Two environments are configured in repo Settings → Environments:

- `development` — no protection, auto-deploys
- `production` — required reviewer = repo owner; the workflow pauses here until you click Approve

## Common pitfalls

- **`data/processed/**` is gitignored.** CI hydrates it from S3 before building. Don't try to commit parquet.
- **Pre-commit hook blocks direct commits to `main`.** Always go via PR.
- **Hatchling needs `README.md` in the image** — already in the Dockerfile, don't remove it.
- **App Runner instance must be ≥ 1 vCPU / 2 GB.** The default 0.25/0.5 OOMs while loading the parquet.
- **Don't push images from your laptop.** Home upload is too slow; let CI do it.
- **Bootstrapping prod the first time:** the prod App Runner can't be created until a `:prod` tag exists in ECR. After the first dev deploy succeeds, manually retag once: `aws ecr batch-get-image ... imageTag=dev | aws ecr put-image ... --image-tag prod`. Then `terraform apply infra/prod/`.
