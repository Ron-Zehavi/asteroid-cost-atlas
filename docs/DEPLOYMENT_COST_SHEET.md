# Deployment plan + cost sheet — Spotlight Mode to production

**Author:** Parallax · **Date:** 2026-06-12 · **Status:** awaiting Ron's approval. Nothing provisioned, nothing pushed.

## Finding first: the stack already exists and prod is LIVE

Probed today (read-only):

| Env | App Runner origin | CloudFront | Status |
|---|---|---|---|
| dev | xgdxw8jhbf…awsapprunner.com | d22ys99gy8q0a7.cloudfront.net | **paused** (404) |
| prod | p6jxczwt29…awsapprunner.com | degvct20vchf3.cloudfront.net | **LIVE, 200 OK** — serving the pre-Spotlight build |

So "deploy" means: **no new resources at all** — push the Spotlight code through the existing CI
(merge to main → image build → one-click promote to prod). The infra (App Runner, CloudFront,
ECR, S3, IAM/OIDC) was provisioned by Ron before today; Terraform state confirms it.

## Exact cost sheet (us-east-1, current published prices)

App Runner: $0.064/vCPU-hr active, $0.007/GB-hr provisioned (idle); 730 hr/month.
Both services are 1 vCPU / 2 GB.

| Item | Calculation | $/month |
|---|---|---|
| Prod App Runner, idle-provisioned 24/7 | 2 GB × $0.007 × 730 | **$10.22** |
| Prod App Runner, active compute (low traffic) | bursts only, ~0–40 active hrs | $0–3 |
| Dev App Runner | **paused** | $0.00 |
| CloudFront (both distros) | within always-free tier (1 TB, 10M req) | $0.00 |
| ECR image storage | ~2–3 GB × $0.10/GB | ~$0.30 |
| S3 data bucket (parquet + logs) | a few GB standard | ~$0.20 |
| CI build minutes | $0.005/min × ~10 min/deploy, occasional | <$0.50 |
| **Total, steady state** | | **≈ $11–14/month** |

Notes:
- The only meaningful cost is prod sitting warm: ~$10.22/mo floor. **Zero-cost option:** pause
  prod too (`aws apprunner pause-service`) and wake it for demos in ~1 min — $0/mo when paused.
- Waking dev for pre-prod smoke testing adds ~$0.33/day while running; pause same day.
- No new paid resource is proposed. Deploying Spotlight changes the *image*, not the bill.

## Proposed sequence (on Ron's go)

1. Feature branch → PR with the Spotlight work (already tested: 116/116, build clean).
2. Merge → CI builds `:dev` image. Optionally `make dev-up`, smoke-test on dev CloudFront, `make dev-down`.
3. Ron reviews the dev URL content (policy: he sees the final content before public).
   *Caveat: prod is already public right now with the old build — strictly, the "nothing public
   until Ron sees it" condition is already moot for the old content; the new content waits for him.*
4. One-click promote to prod in GitHub Actions. Prod CloudFront serves Spotlight.
5. Letter to the mailbox with the final URL and the post-deploy health check.

**Decision needed from Ron:** (a) approve deploy via existing CI as above; (b) keep prod warm
(~$11–14/mo) or pause-when-idle ($0 floor); (c) whether dev smoke-test round is wanted first.
