# 05 · AWS CDK Implementation

Target: AWS CDK v2, TypeScript (Python CDK works equally well; TS gets better autocomplete and is the community default).

## Repo layout

```
infra/cdk/
├── package.json
├── tsconfig.json
├── cdk.json
├── bin/
│   └── app.ts                 # entrypoint
└── lib/
    ├── network-stack.ts
    ├── data-stack.ts
    ├── identity-stack.ts
    ├── compute-stack.ts
    └── observability-stack.ts
```

Each `*-stack.ts` defines one `cdk.Stack`. The entrypoint wires them together and passes outputs across stacks via stack references (no manual SSM lookups).

## `bin/app.ts`

```ts
import * as cdk from "aws-cdk-lib";
import { NetworkStack } from "../lib/network-stack";
import { DataStack } from "../lib/data-stack";
import { IdentityStack } from "../lib/identity-stack";
import { ComputeStack } from "../lib/compute-stack";
import { ObservabilityStack } from "../lib/observability-stack";

const app = new cdk.App();
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region:  process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

const network = new NetworkStack(app, "LinkedinJobNetwork", { env });
const data = new DataStack(app, "LinkedinJobData", {
  env,
  vpc: network.vpc,
  dbSecurityGroup: network.dbSg,
});
const identity = new IdentityStack(app, "LinkedinJobIdentity", {
  env,
  dbInstance: data.dbInstance,
  groqApiKey: process.env.GROQ_API_KEY!,
});
new ComputeStack(app, "LinkedinJobCompute", {
  env,
  vpc: network.vpc,
  webSg: network.webSg,
  imageUri: process.env.IMAGE_URI!,
  ssmParams: identity.ssmParams,
  cognito: identity.cognito,
});
new ObservabilityStack(app, "LinkedinJobObservability", { env });
```

## `lib/network-stack.ts`

```ts
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly webSg: ec2.SecurityGroup;
  public readonly dbSg: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    this.vpc = new ec2.Vpc(this, "Vpc", {
      ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/16"),
      maxAzs: 2,
      natGateways: 0,                   // !! free-tier critical
      subnetConfiguration: [
        { name: "public",  subnetType: ec2.SubnetType.PUBLIC,           cidrMask: 24 },
        { name: "private", subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
      ],
    });

    this.webSg = new ec2.SecurityGroup(this, "WebSg", { vpc: this.vpc, allowAllOutbound: true });
    this.webSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80));
    this.webSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443));

    this.dbSg = new ec2.SecurityGroup(this, "DbSg", { vpc: this.vpc, allowAllOutbound: true });
    this.dbSg.addIngressRule(this.webSg, ec2.Port.tcp(5432), "Postgres from web SG");
  }
}
```

`natGateways: 0` is the key free-tier line — CDK will happily create them by default.

## `lib/data-stack.ts`

```ts
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import { Construct } from "constructs";

interface Props extends cdk.StackProps {
  vpc: ec2.Vpc;
  dbSecurityGroup: ec2.SecurityGroup;
}

export class DataStack extends cdk.Stack {
  public readonly dbInstance: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    this.dbInstance = new rds.DatabaseInstance(this, "Postgres", {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      allocatedStorage: 20,
      storageType: rds.StorageType.GP2,
      multiAz: false,
      publiclyAccessible: false,
      databaseName: "linkedin_job",
      credentials: rds.Credentials.fromGeneratedSecret("linkedin_job"),
      securityGroups: [props.dbSecurityGroup],
      backupRetention: cdk.Duration.days(7),
      deletionProtection: false,            // flip for prod
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
    });
  }
}
```

`fromGeneratedSecret` auto-creates a Secrets Manager secret. Free tier note: that's $0.40/mo. If you want $0, switch to a manually-generated password stored in SSM SecureString (more code, no charge).

## `lib/identity-stack.ts`

```ts
import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as ssm from "aws-cdk-lib/aws-ssm";
import * as rds from "aws-cdk-lib/aws-rds";
import { Construct } from "constructs";

interface Props extends cdk.StackProps {
  dbInstance: rds.DatabaseInstance;
  groqApiKey: string;
}

export class IdentityStack extends cdk.Stack {
  public readonly cognito: {
    userPool: cognito.UserPool;
    client: cognito.UserPoolClient;
    domain: cognito.UserPoolDomain;
  };
  public readonly ssmParams: Record<string, ssm.IParameter>;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    const userPool = new cognito.UserPool(this, "UserPool", {
      selfSignUpEnabled: false,
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: {
        minLength: 12,
        requireUppercase: true,
        requireLowercase: true,
        requireDigits: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const domain = userPool.addDomain("Domain", {
      cognitoDomain: { domainPrefix: `linkedin-job-${this.account.slice(-6)}` },
    });

    const client = userPool.addClient("WebClient", {
      generateSecret: true,
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: ["https://app.example.com/auth/callback"],
        logoutUrls:   ["https://app.example.com/"],
      },
      supportedIdentityProviders: [cognito.UserPoolClientIdentityProvider.COGNITO],
    });

    this.cognito = { userPool, client, domain };

    // Read the auto-generated DB secret and project pieces of it into SSM
    const dbSecret = props.dbInstance.secret!;
    const dbUrlParam = new ssm.StringParameter(this, "DbUrl", {
      parameterName: "/linkedin-job/db/url",
      stringValue: `postgresql+psycopg://linkedin_job:${dbSecret.secretValueFromJson("password").unsafeUnwrap()}@${props.dbInstance.dbInstanceEndpointAddress}:5432/linkedin_job`,
      // NOTE: unsafeUnwrap is fine at synth time because CDK resolves tokens at deploy.
    });

    const groq = new ssm.StringParameter(this, "Groq", {
      parameterName: "/linkedin-job/groq/api_key",
      stringValue: props.groqApiKey,
    });

    const cognitoSecret = new ssm.StringParameter(this, "CognitoClientSecret", {
      parameterName: "/linkedin-job/cognito/client_secret",
      stringValue: client.userPoolClientSecret.unsafeUnwrap(),
    });

    this.ssmParams = { dbUrl: dbUrlParam, groq, cognitoSecret };
  }
}
```

(For real production, replace `StringParameter` + `unsafeUnwrap` with custom-resource-backed SecureString parameters, or keep credentials in Secrets Manager and grant the task role read access there.)

## `lib/compute-stack.ts` — the meat

```ts
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as autoscaling from "aws-cdk-lib/aws-autoscaling";
import * as ssm from "aws-cdk-lib/aws-ssm";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

interface Props extends cdk.StackProps {
  vpc: ec2.Vpc;
  webSg: ec2.SecurityGroup;
  imageUri: string;
  ssmParams: Record<string, ssm.IParameter>;
  cognito: {
    userPool: cognito.UserPool;
    client: cognito.UserPoolClient;
    domain: cognito.UserPoolDomain;
  };
}

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    const cluster = new ecs.Cluster(this, "Cluster", { vpc: props.vpc });

    const asg = new autoscaling.AutoScalingGroup(this, "Asg", {
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      associatePublicIpAddress: true,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      machineImage: ecs.EcsOptimizedImage.amazonLinux2(),
      minCapacity: 1,
      maxCapacity: 1,
      securityGroup: props.webSg,
    });

    cluster.addAsgCapacityProvider(
      new ecs.AsgCapacityProvider(this, "CapacityProvider", { autoScalingGroup: asg })
    );

    const logGroup = new logs.LogGroup(this, "LogGroup", {
      logGroupName: "/ecs/linkedin-job",
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const taskDef = new ecs.Ec2TaskDefinition(this, "TaskDef", {
      networkMode: ecs.NetworkMode.BRIDGE,
    });

    const container = taskDef.addContainer("api", {
      image: ecs.ContainerImage.fromRegistry(props.imageUri),
      memoryLimitMiB: 400,
      cpu: 256,
      logging: ecs.LogDriver.awsLogs({ logGroup, streamPrefix: "api" }),
      environment: {
        LLM_PROVIDER:        "groq",
        COGNITO_REGION:      this.region,
        COGNITO_USER_POOL:   props.cognito.userPool.userPoolId,
        COGNITO_CLIENT_ID:   props.cognito.client.userPoolClientId,
        COGNITO_DOMAIN:      props.cognito.domain.domainName,
      },
      secrets: {
        DATABASE_URL:          ecs.Secret.fromSsmParameter(props.ssmParams.dbUrl),
        GROQ_API_KEY:          ecs.Secret.fromSsmParameter(props.ssmParams.groq),
        COGNITO_CLIENT_SECRET: ecs.Secret.fromSsmParameter(props.ssmParams.cognitoSecret),
      },
    });

    container.addPortMappings({ containerPort: 8000, hostPort: 80 });

    // Grant the task role read access to the SSM params
    for (const p of Object.values(props.ssmParams)) p.grantRead(taskDef.taskRole);

    new ecs.Ec2Service(this, "Service", {
      cluster,
      taskDefinition: taskDef,
      desiredCount: 1,
      minHealthyPercent: 0,
      maxHealthyPercent: 100,
    });
  }
}
```

## Workflow

```bash
cd infra/cdk
npm install
export IMAGE_URI=<account>.dkr.ecr.<region>.amazonaws.com/linkedin-job/api:0.1.0
export GROQ_API_KEY=...

cdk bootstrap        # one-time
cdk diff             # preview
cdk deploy --all     # deploys all five stacks
```

For image bumps:

```bash
# After docker push of the new tag
export IMAGE_URI=<...>/linkedin-job/api:0.2.0
cdk deploy LinkedinJobCompute
```

## Pros / cons (vs Terraform)

See [07-terraform-vs-cdk.md](07-terraform-vs-cdk.md).
