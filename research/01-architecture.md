# 01 · Target Architecture

## Goals

1. Run the FastAPI app (`uvicorn app.main:app`) on AWS without leaving the free tier.
2. Move persistence from SQLite to RDS Postgres.
3. Front the app with Cognito for user authentication (replacing the current "no auth" posture).
4. Keep scheduled scrapes running (APScheduler equivalent).
5. Keep everything reproducible via IaC (Terraform **or** CDK).

## High-level diagram

```
                     ┌────────────────────────────────────────────────┐
                     │                  AWS Region                    │
                     │                                                │
   Browser ──HTTPS──►│  ┌────────────┐         ┌──────────────────┐  │
                     │  │  Cognito   │◄──OIDC──┤  ALB (optional)  │  │
                     │  │ User Pool  │         │   :443           │  │
                     │  └────────────┘         └─────────┬────────┘  │
                     │                                    │           │
                     │                          ┌─────────▼────────┐  │
                     │                          │  ECS Service     │  │
                     │                          │  (1 task)        │  │
                     │                          │  ┌────────────┐  │  │
                     │                          │  │ FastAPI    │  │  │
                     │                          │  │ container  │  │  │
                     │                          │  │ on EC2     │  │  │
                     │                          │  │ t3.micro   │  │  │
                     │                          │  └─────┬──────┘  │  │
                     │                          └────────┼─────────┘  │
                     │                                   │            │
                     │                          ┌────────▼─────────┐  │
                     │                          │ RDS Postgres     │  │
                     │                          │ db.t3.micro      │  │
                     │                          │ private subnet   │  │
                     │                          └──────────────────┘  │
                     │                                                │
                     │  Secrets Manager / SSM ─── ECR ─── CloudWatch  │
                     │                                                │
                     │  EventBridge Scheduler ──► ECS RunTask         │
                     │  (scrape job, optional alternative to in-app   │
                     │   APScheduler)                                 │
                     └────────────────────────────────────────────────┘
```

## Component breakdown

### VPC

- Single VPC, **single AZ** (free tier doesn't care about HA; multi-AZ doubles cost).
- One **public subnet** for the EC2 container instance and ALB.
- One **private subnet** for RDS (RDS requires a DB subnet group with ≥2 subnets in 2 AZs — you can create the second private subnet in a second AZ but **leave it empty**; RDS itself stays Single-AZ).
- No NAT Gateway (≈ $32/mo, not free). Outbound calls from the container go via the public subnet's IGW with a public IP on the EC2 host.

### Compute — ECS on EC2

- ECS cluster `linkedin-job-cluster`.
- One EC2 container instance, `t2.micro` or `t3.micro`, Amazon Linux 2 ECS-optimized AMI.
- One ECS service running one task definition with the FastAPI container.
- Auto-assign public IP on the host so it can pull from ECR and reach the public internet (JobSpy, Groq, etc.).
- Task definition: `awsvpc` network mode (cleaner SGs) or `bridge` (simpler on a single host — pick `bridge` for free-tier simplicity).

### Load balancing — optional

- For the cheapest setup, expose port 80/443 directly on the EC2 host via its security group.
- ALB is **not** free (≈ $16/mo + LCUs). Skip unless you need TLS termination + multiple targets.
- TLS: use **Caddy** as a sidecar (auto Let's Encrypt) on the same host, or front with CloudFront (1 TB egress free always) + the host's public IP/EIP.

### Database — RDS Postgres

- Engine: Postgres 16.
- Class: `db.t3.micro` (x86) or `db.t4g.micro` (ARM, slightly cheaper) — both eligible for the 12-month free tier (750 hrs/month).
- Storage: 20 GB gp2 (free tier max).
- Single-AZ, no read replica, 7-day automated backups (within free tier: 20 GB backup storage).
- Publicly accessible: **no**. Security group only accepts traffic from the ECS host's SG on `5432`.

### Auth — Cognito User Pool

- One User Pool, hosted UI enabled.
- One App Client (confidential, with client secret).
- Callback URL: `https://<your-host>/auth/callback`.
- Free tier: **50,000 MAUs always free** (no 12-month cliff). This is the cheapest part of the stack.
- App integrates via OIDC (Authorization Code + PKCE). Add an OIDC middleware to FastAPI (e.g., `authlib`, `fastapi-users`, or `starlette-oauth2`).

### Secrets

- **AWS Secrets Manager** for the RDS password and the Cognito client secret (rotation-friendly, $0.40/secret/month — not free, but $0.80 for both is acceptable). Alternative: **SSM Parameter Store SecureString** is free.
- Recommendation: SSM SecureString for everything to stay $0.

### Image registry

- **ECR private repo** — 500 MB storage free for 12 months. Keep the image ≤ 500 MB by using a slim Python base and a multi-stage build (Playwright bloats the image fast; consider not bundling Playwright into the API container — see [06-app-readiness.md](06-app-readiness.md)).

### Observability

- **CloudWatch Logs** — 5 GB ingestion + 5 GB storage free always. Stream container stdout via the `awslogs` log driver.
- **CloudWatch Metrics** — basic EC2/RDS metrics free.

### Scheduler

- **Option A (default):** keep APScheduler in-process. Works because there's exactly one ECS task.
- **Option B (more cloud-native):** EventBridge Scheduler rule → `ecs:RunTask` against a separate "worker" task definition that runs `scripts/run_scrape.py` and exits. Lets you scale the web service independently. Both options are free.

## Trust boundaries

| Boundary | Crossing | Control |
|----------|----------|---------|
| Internet → host | 443 (or 80) | Host SG, Cognito session cookie |
| Host → RDS | 5432 | DB SG allows only host SG |
| Host → AWS APIs | HTTPS | IAM role on the EC2 instance + task role |
| Host → external (Groq, JobSpy targets) | HTTPS egress | None required; outbound open |

## What we explicitly do NOT use

- Fargate (no free tier).
- NAT Gateway (not free).
- ALB (not free; skip unless needed).
- Multi-AZ RDS (doubles cost).
- Aurora Serverless (not free tier eligible for Postgres in the same way).
- Elastic Beanstalk (adds an extra abstraction we don't need; ECS is direct).
