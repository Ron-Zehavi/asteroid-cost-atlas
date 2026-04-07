# Deploy

Live URL: <https://5z4pptzp3t.us-east-1.awsapprunner.com>

## Daily flow

```bash
# 1. Develop
git checkout -b feature/whatever
# ...edit code...
make test && make lint && make typecheck
./start.sh                          # smoke test locally

# 2. Ship
git push -u origin feature/whatever
gh pr create --base main
# ...merge PR on GitHub UI...

# 3. Wait ~5 min for CI to build & push image, then trigger redeploy
ARN=$(aws apprunner list-services --region us-east-1 --profile asteroid \
  --query "ServiceSummaryList[?ServiceName=='asteroid-cost-atlas'].ServiceArn | [0]" \
  --output text)
aws apprunner start-deployment --service-arn "$ARN" --region us-east-1 --profile asteroid

# 4. Verify
curl https://5z4pptzp3t.us-east-1.awsapprunner.com/api/health
```

## Refresh data

The container bakes the parquet from S3 at build time. To update:

```bash
make pipeline                       # generates new atlas_<date>.parquet locally
aws s3 sync data/processed/ s3://asteroid-cost-atlas-data-975050282139/processed/ \
  --profile asteroid --exclude "*" --include "atlas_*.parquet"

# Trigger a CI rebuild (any merge to main works; or push an empty commit):
git commit --allow-empty -m "Refresh data" && git push
```

## Resources

| Resource | Name |
|---|---|
| AWS profile | `asteroid` (us-east-1) |
| App Runner service | `asteroid-cost-atlas` (1 vCPU / 2 GB) |
| ECR repo | `975050282139.dkr.ecr.us-east-1.amazonaws.com/asteroid-cost-atlas` |
| S3 data bucket | `asteroid-cost-atlas-data-975050282139` |
| GitHub Actions IAM role | `asteroid-cost-atlas-github-actions` (OIDC, `refs/heads/main` only) |
| Logs | `/aws/apprunner/asteroid-cost-atlas/<id>/application` |

## Logs

```bash
SVC=$(aws apprunner list-services --region us-east-1 --profile asteroid \
  --query 'ServiceSummaryList[0].ServiceArn' --output text)
LOG="/aws/apprunner/asteroid-cost-atlas/$(echo $SVC | awk -F/ '{print $NF}')/application"
aws logs tail "$LOG" --region us-east-1 --profile asteroid --follow
```

## Infra changes

Terraform lives under `infra/`. Apply manually from your laptop:

```bash
cd infra
AWS_PROFILE=asteroid terraform plan
AWS_PROFILE=asteroid terraform apply
```

CI does **not** run terraform — only image build/push/deploy.

## Common pitfalls

- **`data/processed/**` is gitignored.** CI hydrates it from S3 before building. Don't try to commit parquet.
- **Pre-commit hook blocks direct commits to `main`.** Always go via PR.
- **Hatchling needs `README.md` in the image** — already in the Dockerfile, don't remove it.
- **App Runner instance must be ≥ 1 vCPU / 2 GB.** The default 0.25/0.5 OOMs while loading the parquet.
- **Don't push images from your laptop.** Home upload is too slow; let CI do it.
