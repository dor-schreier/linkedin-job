# AWS Deployment Research

Research notes for deploying the `linkedin-job` FastAPI app to AWS using ECS, RDS Postgres, and Cognito under the AWS Free Tier. Two IaC paths are documented: Terraform and AWS CDK.

## Files

| # | File | Purpose |
|---|------|---------|
| 1 | [01-architecture.md](01-architecture.md) | Target architecture, network topology, component responsibilities |
| 2 | [02-free-tier-considerations.md](02-free-tier-considerations.md) | What each service costs, what stays free, and the trade-offs forced by the free tier |
| 3 | [03-deployment-plan.md](03-deployment-plan.md) | Ordered, step-by-step deployment plan (IaC-agnostic) |
| 4 | [04-terraform.md](04-terraform.md) | Terraform implementation: module layout, state, sample resources |
| 5 | [05-aws-cdk.md](05-aws-cdk.md) | AWS CDK implementation: stack layout, constructs, sample code |
| 6 | [06-app-readiness.md](06-app-readiness.md) | Changes required in the application code to be cloud-ready (SQLite → Postgres, scheduler, secrets, auth, container image) |
| 7 | [07-terraform-vs-cdk.md](07-terraform-vs-cdk.md) | Side-by-side comparison and recommendation |

## TL;DR

- **Compute:** ECS on **EC2 (t2.micro / t3.micro)** — not Fargate. Fargate has no always-free or 12-month free tier; EC2 has 750 hours/month free for 12 months.
- **DB:** RDS Postgres `db.t3.micro` or `db.t4g.micro`, Single-AZ, 20 GB gp2 (12-month free tier).
- **Auth:** Cognito User Pool — 50,000 MAUs in the always-free tier (no 12-month cliff).
- **Networking:** Single AZ, public subnet for the EC2 host, RDS in a private subnet, no NAT Gateway (NAT is **not** free → avoid).
- **Image registry:** ECR private repo (500 MB free for 12 months) or Docker Hub if image is large.
- **State store for IaC:** S3 + DynamoDB lock table (both within free tier at this scale).
- **Scheduler:** APScheduler in-process works on a single-host ECS service; if you scale beyond 1 task, move scheduled scrapes to **EventBridge Scheduler → ECS RunTask**.
