# 07 · Terraform vs AWS CDK — Comparison & Recommendation

You asked for both options. Here's how they compare for *this specific deployment*.

## At a glance

| Dimension | Terraform | AWS CDK |
|---|---|---|
| Language | HCL (DSL) | TypeScript / Python / Java / Go / C# |
| State | S3 + DynamoDB lock (you manage) | CloudFormation (AWS manages) |
| Provider scope | Multi-cloud + 3000+ providers | AWS only (CDK for Kubernetes/Terraform exist but are separate tools) |
| Drift detection | `terraform plan` | `cdk diff` + CloudFormation drift |
| Abstraction level | Resources only (modules optional) | High-level Constructs (L2/L3) collapse boilerplate |
| Loops / conditionals | `for_each`, `count`, ternaries — adequate | Full programming language — much more flexible |
| Refactoring | `moved` blocks, painful but works | Logical-ID-preserving via construct paths, painful if you reorganize |
| Secrets handling | Pass via vars, must avoid plaintext in state | Same problem; tokens defer to deploy time |
| Learning curve | Lower — declarative HCL | Higher — must know TS/Python AND CDK idioms |
| Community / examples for AWS | Massive | Massive, AWS-blessed |
| Local toolchain | Single `terraform` binary | Node + cdk CLI + your language toolchain |
| CI integration | Trivial | Trivial, but `cdk synth` is slower |
| Lock-in | Lower (HCL is portable in principle) | Higher (CloudFormation under the hood) |
| Free-tier defaults | None — you must explicitly skip NATs | **Beware**: L2 constructs (`Vpc`) create NAT Gateways by default |

## Where each shines for *this* project

### Terraform wins on
- **Transparent resource control.** You write `aws_vpc`, you get exactly one VPC. No hidden NAT, no surprise log groups.
- **State portability.** Easy to inspect, easy to import existing resources.
- **One tool, multiple clouds.** If you ever add Cloudflare DNS, Fly.io, or anything non-AWS, the same tool covers it.
- **Smaller blast radius from mistakes.** Plan output is line-by-line resources; no synthesized CloudFormation translation layer.

### CDK wins on
- **Less boilerplate per stack.** `new ecs.Ec2Service(...)` collapses what would be 5–10 Terraform resources (cluster + ASG + capacity provider + task def + service + IAM).
- **First-class IDE support.** Autocomplete on resource props, refactors, types.
- **Easy to abstract.** If you grow into multiple envs/services, writing a `LinkedinJobService` construct that wraps the whole thing is one TS class.
- **Bootstrapping is faster.** `cdk init app` gives you a working scaffold in seconds.

## Free-tier specific footguns

Both tools will happily create non-free-tier resources unless you stop them:

### Terraform
- The `aws_vpc` resource doesn't create NAT — only an explicit `aws_nat_gateway` does. Safe by default.
- `aws_db_instance` has no Multi-AZ by default — safe.
- You must explicitly *not* add `aws_lb` resources.

### CDK
- `new ec2.Vpc(this, "Vpc")` creates **1 NAT Gateway per AZ by default** — **must pass `natGateways: 0`** or you immediately blow the free tier.
- `new ecs.Cluster(this, ...)` is fine but `ApplicationLoadBalancedEc2Service` (a higher-level construct) adds an ALB. Don't use it.
- `DatabaseInstance` defaults to Single-AZ — safe.
- `aws_cdk_lib/aws_ec2.Vpc` will also create flow logs to a new log group if you ask for them — small cost.

**The CDK-default-NAT trap has cost more people their first month than any other issue.** If you go CDK, that one line is non-negotiable.

## Recommendation

**Use Terraform for this project**, with these reasons specific to your context:

1. **Resource transparency matters here.** A free-tier deployment is sensitive to every line item. Terraform's lower abstraction makes it easier to be sure you didn't accidentally create a paid resource.
2. **Single-binary toolchain.** Your repo is Python; adding Node + npm + a TypeScript build step just for IaC is overhead.
3. **No multi-environment complexity yet.** CDK's "real programming language" advantage pays off when you have many stacks, many envs, many shared abstractions. You have one app, one env.
4. **Easier handover / reading later.** HCL is more readable than synthesized CloudFormation when debugging six months from now.
5. **`tfstate` in S3 is fine.** You don't need the CloudFormation-managed state CDK provides.

**Pick CDK instead if:**
- You're already a TypeScript developer and HCL feels alien.
- You expect to grow several services and want construct-level reuse.
- You like CloudFormation events visibility in the AWS console.

Either way, both implementations in this research package are deployable as-is once you wire in the secrets and image URI.

## What you should NOT do

- Use **both** in the same account, on the same resources. Each owns its state; collisions are painful.
- Use **CloudFormation by hand** (your prompt mentioned "ecs (cloud formation)"). CDK already generates CloudFormation under the hood, so picking CDK *is* picking CloudFormation, just authored more comfortably. Writing raw CFN YAML by hand for this is masochism — skip it.
- Use **Elastic Beanstalk, Lightsail Containers, or AppRunner**. They're simpler at first but lock you out of the explicit ECS/RDS/Cognito stack you asked for and have less generous free tiers.
