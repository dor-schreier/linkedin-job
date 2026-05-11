# 02 · Free Tier Considerations

AWS Free Tier comes in three flavors:

- **12-month free** — only after first-ever AWS account creation; expires.
- **Always free** — permanent, with per-month caps.
- **Trials** — short-lived, ignore for production planning.

## Per-service breakdown

| Service | Tier type | Free allowance | What we use | Risk of overage |
|---------|-----------|----------------|-------------|-----------------|
| EC2 (t2/t3.micro Linux) | 12-month | 750 hrs/month | 1 instance 24/7 = 730 hrs | None if you keep 1 instance. |
| EBS gp2 | 12-month | 30 GB | Root vol ~8 GB | None. |
| RDS (db.t3.micro or db.t4g.micro Postgres) | 12-month | 750 hrs/month, 20 GB storage, 20 GB backups | 1 instance, 20 GB | None if Single-AZ. Multi-AZ doubles usage. |
| Cognito User Pools | Always free | 50,000 MAUs | App users | Effectively zero for personal use. |
| ECR | 12-month | 500 MB private storage | 1 image | Keep image small. Playwright base can exceed 1 GB. |
| CloudWatch Logs | Always free | 5 GB ingest + 5 GB storage | App logs | Set retention to 7–14 days. |
| Data transfer out | Always free | 100 GB/month (region-aware) | HTML responses | Low risk. |
| S3 (for IaC state) | 12-month | 5 GB | Terraform state ~MB | None. |
| DynamoDB (Terraform lock) | Always free | 25 GB + 25 WCU/RCU | A few writes/day | None. |
| SSM Parameter Store (standard) | Always free | 10,000 params | < 20 params | None. |
| Secrets Manager | None | $0.40/secret/month | Optional | Prefer SSM. |
| ALB | None | — | Skip | $16+/mo if used. |
| NAT Gateway | None | — | Skip | $32+/mo if used. |
| Fargate | None | — | Skip | Pay per vCPU-second. |
| EventBridge Scheduler | Always free | 14M invocations/month | A few scrape triggers | None. |

## Constraints this imposes on the design

1. **One EC2 host, one AZ.** Plan for downtime during deploys (rolling deploy on a single host = momentary unavailability; acceptable for a personal job-search tool).
2. **No NAT.** The ECS host must live in a public subnet to reach ECR and external APIs. RDS stays private — that's fine because RDS doesn't need outbound internet.
3. **No ALB by default.** Either expose ports on the EC2 host with a security group, or put CloudFront in front for free TLS + caching.
4. **Image size discipline.** Playwright base images are ~1.5 GB. If you must keep Playwright in the API image, you'll blow the 500 MB ECR free quota. Options:
   - Move the Playwright-using code (`scrapers/search_backends.py` Playwright backend) to a **separate** image only built when needed, or
   - Default `GOOGLE_SEARCH_BACKEND=ddgs` in production so the API image doesn't need Playwright at all.
5. **No Multi-AZ RDS.** Single-AZ is fine for free tier. Accept the failover risk.
6. **Backups.** RDS automated backups are free up to 20 GB, but **snapshot storage after instance deletion is billed** — clean up on teardown.

## Known "gotchas"

- **The 750-hour budget is per service across all instances.** Two t3.micros for 750 hrs each = 1500 hrs = 750 hrs over the free tier.
- **Free tier resets monthly**, not yearly. Don't binge in week 1 of a month.
- **RDS storage type:** stay on `gp2`. `gp3` is *not* free-tier eligible for RDS.
- **Cognito advanced security features (ASF)** are not free. Leave them off.
- **CloudFront** has 1 TB out + 10M requests free **always**. Useful and effectively zero cost for this app.
- **Public IPv4 addresses now cost $0.005/hour (~$3.60/mo)** as of Feb 2024. The EC2 host's public IPv4 = ~$3.60/month. There is no free-tier exemption. Options:
  - Accept the $3.60/mo cost.
  - Use IPv6-only + dual-stack (free, but client support is mixed).
  - Use CloudFront in front (the EC2 origin can still need a public IP).
- **Egress to internet** is 100 GB/mo always-free across the account. Should be plenty.

## Estimated monthly cost

| Scenario | Year 1 | Year 2+ |
|----------|--------|---------|
| Bare-minimum (1× t3.micro, RDS t3.micro, public IPv4, SSM secrets) | **~$3.60** (just the IPv4) | **~$30–40** (EC2 + RDS + IPv4) |
| With ALB | +$16 | +$16 |
| With NAT | +$32 | +$32 |
| With Multi-AZ RDS | +cost of second RDS instance | +cost of second RDS instance |

The single biggest year-2 cliff is RDS: ~$13/mo for `db.t3.micro` + ~$2.30 for 20 GB gp2. Plan to either accept that, move to RDS reserved instances, or migrate to an Aurora Serverless v2 with minimum ACUs.
