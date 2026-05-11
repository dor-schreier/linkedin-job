# 04 · Terraform Implementation

Target: Terraform ≥ 1.6, AWS provider ≥ 5.x.

## Repo layout

```
infra/terraform/
├── backend.tf            # S3 + DynamoDB state config
├── providers.tf          # aws provider, default tags
├── variables.tf          # input vars (region, project, image_tag, ...)
├── outputs.tf            # app URL, cognito IDs, DB endpoint
├── main.tf               # composition (calls modules)
└── modules/
    ├── network/          # VPC, subnets, SGs
    ├── data/             # RDS + DB subnet group + parameter group
    ├── identity/         # Cognito user pool, app client, SSM params
    ├── compute/          # ECS cluster, ASG, launch template, task def, service
    └── observability/    # log group, billing alarm
```

Each module exposes a thin interface (a few inputs, a few outputs). Root `main.tf` wires them together.

## `backend.tf`

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket         = "linkedin-job-tfstate-<account-id>"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "linkedin-job-tflock"
    encrypt        = true
  }
}
```

## `providers.tf`

```hcl
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "linkedin-job"
      ManagedBy = "terraform"
      Env       = var.env
    }
  }
}
```

## `variables.tf` (root, abbreviated)

```hcl
variable "region"    { type = string  default = "us-east-1" }
variable "env"       { type = string  default = "prod" }
variable "image_uri" { type = string }  # passed at apply time
variable "db_password" {
  type      = string
  sensitive = true
}
variable "groq_api_key" {
  type      = string
  sensitive = true
}
```

## Module: `network`

```hcl
# modules/network/main.tf
resource "aws_vpc" "this" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.region}a"
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.region}b"
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "web" {
  name   = "linkedin-job-web"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db" {
  name   = "linkedin-job-db"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Outputs: `vpc_id`, `public_subnet_id`, `private_subnet_ids` (list), `web_sg_id`, `db_sg_id`.

## Module: `data` (RDS)

```hcl
resource "aws_db_subnet_group" "this" {
  name       = "linkedin-job-db"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "this" {
  identifier              = "linkedin-job"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  storage_type            = "gp2"
  db_name                 = "linkedin_job"
  username                = "linkedin_job"
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [var.db_sg_id]
  multi_az                = false
  publicly_accessible     = false
  backup_retention_period = 7
  skip_final_snapshot     = true   # set to false for prod
  deletion_protection     = false  # set to true for prod
  apply_immediately       = true
}
```

## Module: `identity` (Cognito + SSM)

```hcl
resource "aws_cognito_user_pool" "this" {
  name = "linkedin-job-users"
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
  }
  account_recovery_setting {
    recovery_mechanism { name = "verified_email" priority = 1 }
  }
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = "linkedin-job-${random_id.suffix.hex}"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "random_id" "suffix" { byte_length = 4 }

resource "aws_cognito_user_pool_client" "this" {
  name                                 = "linkedin-job-web"
  user_pool_id                         = aws_cognito_user_pool.this.id
  generate_secret                      = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = [var.callback_url]
  logout_urls                          = [var.logout_url]
  supported_identity_providers         = ["COGNITO"]
}

resource "aws_ssm_parameter" "db_url" {
  name  = "/linkedin-job/db/url"
  type  = "SecureString"
  value = "postgresql+psycopg://${var.db_user}:${var.db_password}@${var.db_host}:5432/${var.db_name}"
}

resource "aws_ssm_parameter" "groq" {
  name  = "/linkedin-job/groq/api_key"
  type  = "SecureString"
  value = var.groq_api_key
}

resource "aws_ssm_parameter" "cognito_client_secret" {
  name  = "/linkedin-job/cognito/client_secret"
  type  = "SecureString"
  value = aws_cognito_user_pool_client.this.client_secret
}
```

## Module: `compute` (ECS on EC2)

Key resources (abbreviated):

```hcl
resource "aws_ecs_cluster" "this" {
  name = "linkedin-job-cluster"
}

data "aws_ssm_parameter" "ecs_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
}

resource "aws_iam_role" "ecs_instance" {
  name = "linkedin-job-ecs-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_instance" {
  role       = aws_iam_role.ecs_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ecs_instance" {
  name = "linkedin-job-ecs-instance"
  role = aws_iam_role.ecs_instance.name
}

resource "aws_launch_template" "ecs" {
  name_prefix            = "linkedin-job-"
  image_id               = data.aws_ssm_parameter.ecs_ami.value
  instance_type          = "t3.micro"
  vpc_security_group_ids = [var.web_sg_id]
  iam_instance_profile { name = aws_iam_instance_profile.ecs_instance.name }
  user_data = base64encode(<<-EOT
    #!/bin/bash
    echo ECS_CLUSTER=${aws_ecs_cluster.this.name} >> /etc/ecs/ecs.config
  EOT
  )
}

resource "aws_autoscaling_group" "ecs" {
  name                = "linkedin-job-asg"
  min_size            = 1
  max_size            = 1
  desired_capacity    = 1
  vpc_zone_identifier = [var.public_subnet_id]
  launch_template {
    id      = aws_launch_template.ecs.id
    version = "$Latest"
  }
  tag {
    key                 = "AmazonECSManaged"
    value               = "true"
    propagate_at_launch = true
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "linkedin-job-api"
  network_mode             = "bridge"
  requires_compatibilities = ["EC2"]
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn
  cpu                      = "256"
  memory                   = "400"
  container_definitions = jsonencode([{
    name      = "api"
    image     = var.image_uri
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 80, protocol = "tcp" }]
    environment = [
      { name = "LLM_PROVIDER",        value = "groq" },
      { name = "COGNITO_REGION",      value = var.region },
      { name = "COGNITO_USER_POOL",   value = var.cognito_user_pool_id },
      { name = "COGNITO_CLIENT_ID",   value = var.cognito_client_id },
      { name = "COGNITO_DOMAIN",      value = var.cognito_domain },
    ]
    secrets = [
      { name = "DATABASE_URL",          valueFrom = var.ssm_db_url_arn },
      { name = "GROQ_API_KEY",          valueFrom = var.ssm_groq_arn },
      { name = "COGNITO_CLIENT_SECRET", valueFrom = var.ssm_cognito_secret_arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "linkedin-job-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "EC2"
  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 0
}
```

## Workflow

```bash
cd infra/terraform
terraform init
terraform plan -var "image_uri=..." -var "db_password=..." -var "groq_api_key=..."
terraform apply -var "..."     # same vars
terraform output app_url
```

For day-to-day image bumps, only the `image_uri` var changes → `terraform apply` produces a new task def revision and the service rolls.

## State and secrets hygiene

- **Never** commit `terraform.tfstate` or `.tfvars` files containing secrets.
- Pass secret vars via env vars: `TF_VAR_db_password=...`.
- Or use `terraform apply -var-file=secrets.auto.tfvars` with that file gitignored.
- Even better: keep secrets in SSM/Secrets Manager pre-created, and use `data` sources to read them — Terraform never sees the plaintext.

## Pros / cons (vs CDK)

See [07-terraform-vs-cdk.md](07-terraform-vs-cdk.md).
