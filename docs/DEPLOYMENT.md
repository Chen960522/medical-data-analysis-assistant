# 部署文档 — 医学数据分析助手

本文档描述医学数据分析助手平台在 AWS 上的生产部署流程。部署统一使用区域 **us-east-1**。

## 目录

- [1. 架构与资源清单](#1-架构与资源清单)
- [2. 前置条件](#2-前置条件)
- [3. 部署前检查清单](#3-部署前检查清单)
- [4. 部署流程](#4-部署流程)
- [5. 配置与密钥注入](#5-配置与密钥注入)
- [6. 部署后验证](#6-部署后验证)
- [7. 回滚与销毁](#7-回滚与销毁)
- [8. 故障排查](#8-故障排查)

---

## 1. 架构与资源清单

| 层级 | 技术 | 部署位置 |
|------|------|----------|
| 前端 | React 18 + TypeScript | S3 + CloudFront |
| 后端 API | Python FastAPI | ECS Fargate（2 vCPU / 4GB，自动扩缩 2–10） |
| 自研 MCP Server | 图表生成 / 报告生成 / CNKI 检索 | ECS Fargate（1 vCPU / 2GB，自动扩缩 2–6） |
| AI Agent | Strands Agents SDK + Claude Sonnet | Amazon Bedrock AgentCore Runtime |
| 关系数据库 | PostgreSQL 15 | RDS（db.r6g.large，Multi-AZ，KMS 加密） |
| 缓存 | Redis 7 | ElastiCache（cache.r6g.large，传输/静态加密） |
| 对象存储 | 数据文件 / 报告 / 前端静态资源 | S3（KMS 加密、强制 SSL） |
| 密钥与加密 | KMS（自动轮换）、Secrets Manager | 全局 |

CDK 栈及依赖顺序：

| 栈名 | 资源 |
|------|------|
| `MedicalAnalysis-Network` | VPC（10.0.0.0/16）、3 层子网、NAT、VPC Endpoints（S3 / ECR / CloudWatch / Bedrock） |
| `MedicalAnalysis-Security` | KMS 主加密密钥、JWT 签名密钥（Secrets Manager） |
| `MedicalAnalysis-Database` | RDS PostgreSQL 15（Multi-AZ）、ElastiCache Redis 7 |
| `MedicalAnalysis-Storage` | S3 数据桶、报告桶 |
| `MedicalAnalysis-Compute` | ECS Fargate 集群、ALB、API 服务、MCP 服务 |
| `MedicalAnalysis-Cdn` | 前端 S3 桶 + CloudFront 分发 |

依赖顺序：`Network → Security → Database / Storage / Compute → Cdn`

---

## 2. 前置条件

- AWS 账号，具备创建 VPC、RDS、ElastiCache、ECS、S3、CloudFront、KMS、Secrets Manager、IAM 的权限。
- AWS CLI v2，已通过 `aws configure` 配置目标账号凭证。
- Node.js >= 18 与 AWS CDK CLI：`npm install -g aws-cdk`。
- 本地 Docker（CDK 在本地构建后端与 MCP 镜像并推送至 ECR）。
- 一张位于 **us-east-1**、状态为 `Issued` 的 ACM 证书（用于 ALB HTTPS 监听器）。
- 在 us-east-1 已开通 Amazon Bedrock 的 Claude Sonnet 模型访问权限。

---

## 3. 部署前检查清单

执行 `cdk deploy` 前逐项确认：

- [ ] AWS 凭证可用：`aws sts get-caller-identity` 返回目标账号。
- [ ] CDK CLI 可用：`cdk --version`。
- [ ] CDK 已引导到 us-east-1：`cdk bootstrap aws://<ACCOUNT_ID>/us-east-1`。
- [ ] 本地 Docker 守护进程在运行：`docker info` 正常。
- [ ] ACM 证书位于 us-east-1 且状态为 `Issued`。
- [ ] Bedrock 在 us-east-1 已启用 Claude Sonnet（`anthropic.claude-sonnet-4-...`）。
- [ ] 区域配额充足：可创建 VPC、2 个 NAT 网关、RDS（db.r6g.large）、ElastiCache（cache.r6g.large）、ECS Fargate。

> 成本提示：本架构含 Multi-AZ RDS、2 节点 ElastiCache、2 个 NAT 网关、ALB 与 CloudFront，按小时计费。停用时请按 [第 7 节](#7-回滚与销毁) 清理。

---

## 4. 部署流程

### 4.1 准备 CDK 环境

```bash
cd infrastructure
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cdk bootstrap aws://<ACCOUNT_ID>/us-east-1
```

### 4.2 部署基础设施

容器镜像由 CDK 资产（`ecs.ContainerImage.from_asset`）自动构建并推送至 ECR，无需手动 `docker build` / `docker push`：

| 服务 | Dockerfile |
|------|-----------|
| API 服务 | `backend/Dockerfile` |
| MCP 服务 | `mcp-servers/Dockerfile` |

部署全部栈到 us-east-1：

```bash
cdk deploy --all \
  -c region=us-east-1 \
  -c bedrock_region=us-east-1 \
  -c agentcore_region=us-east-1 \
  -c certificate_arn=arn:aws:acm:us-east-1:<ACCOUNT_ID>:certificate/<CERT_ID> \
  -c agentcore_runtime_arn=arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:runtime/medical-analysis
```

参数说明：

- `region` / `bedrock_region` / `agentcore_region`：统一为 us-east-1。
- `certificate_arn`：ALB HTTPS（TLS 1.2+）监听器证书，必须位于 us-east-1。
- `agentcore_runtime_arn`：注入到 API 容器的 `APP_AGENTCORE_RUNTIME_ARN`。首次可省略此参数，待 [4.4](#44-部署-ai-agentbedrock-agentcore) 完成后回填并重部署 Compute 栈：

  ```bash
  cdk deploy MedicalAnalysis-Compute -c region=us-east-1 \
    -c certificate_arn=<arn> -c agentcore_runtime_arn=<arn>
  ```

部署完成后，从 `cdk deploy` 输出或 CloudFormation 控制台记录：ALB DNS、CloudFront 域名、前端 S3 桶名、CloudFront 分发 ID、RDS Endpoint。

### 4.3 数据库迁移

从可访问私有数据子网的环境（堡垒机或一次性 ECS 任务）执行 Alembic 迁移。RDS 凭证由 CDK 自动生成并存入 Secrets Manager。

```bash
cd backend
APP_DB_HOST=<rds-endpoint> \
APP_DB_PORT=5432 \
APP_DB_NAME=medical_analysis \
APP_DB_USER=<secrets-manager-username> \
APP_DB_PASSWORD=<secrets-manager-password> \
  alembic upgrade head
```

### 4.4 部署 AI Agent（Bedrock AgentCore）

```bash
cd backend
pip install bedrock-agentcore-starter-toolkit
agentcore configure --entrypoint app/agent/entrypoint.py --non-interactive
agentcore deploy
```

部署返回的 Runtime ARN 即上文 `agentcore_runtime_arn`，回填后重部署 Compute 栈（见 4.2）。

### 4.5 部署前端

```bash
cd frontend
npm install
npm run build
aws s3 sync dist/ s3://<FRONTEND_BUCKET>/ --delete
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

---

## 5. 配置与密钥注入

后端配置由 `backend/app/core/config.py` 管理，变量前缀 **`APP_`**。生产环境由 `ComputeStack` 自动注入 ECS 任务定义，**无需手工维护 `.env`**：

- **普通配置（`environment`）**：`APP_DB_HOST`、`APP_DB_PORT`、`APP_DB_NAME`、`APP_REDIS_URL`（`rediss://`）、`APP_S3_BUCKET_NAME`、`APP_AWS_REGION`、`APP_BEDROCK_REGION`、`APP_AGENTCORE_REGION`、`APP_AGENTCORE_RUNTIME_ARN`。
- **密钥（`secrets`，来自 Secrets Manager，不以明文出现在任务定义）**：
  - `APP_DB_USER` / `APP_DB_PASSWORD` —— RDS 自动生成的凭证密钥；
  - `APP_JWT_SECRET_KEY` —— `SecurityStack` 生成的 64 位随机密钥。

> 当 `APP_DB_HOST` 存在时，后端用 `HOST/PORT/NAME/USER/PASSWORD` 拼装数据库连接串，密码无需出现在单一明文 URL 中。

关键配置项参考（默认值见 `config.py`）：

| 变量 | 生产取值 | 说明 |
|------|----------|------|
| `APP_AWS_REGION` / `APP_BEDROCK_REGION` / `APP_AGENTCORE_REGION` | `us-east-1` | 由 CDK context 注入 |
| `APP_BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-20250514-v1:0` | Bedrock 模型 ID |
| `APP_JWT_ACCESS_TOKEN_EXPIRE_HOURS` | `24` | JWT 过期时间 |
| `APP_BCRYPT_COST_FACTOR` | `12` | bcrypt 成本因子 |
| `APP_MAX_LOGIN_ATTEMPTS` / `APP_ACCOUNT_LOCKOUT_MINUTES` | `5` / `15` | 登录锁定策略 |
| `APP_S3_MAX_FILE_SIZE` | `104857600` | 数据文件上限 100MB |

ECS 任务角色权限（由 CDK 配置）：S3 读写（数据/报告桶）、KMS 加解密、Bedrock（`InvokeModel`、`InvokeModelWithResponseStream`、`InvokeAgentRuntime`）。

---

## 6. 部署后验证

```bash
# API 健康检查（经 ALB / 域名）
curl https://<ALB_或域名>/health
# 期望：{"status": "healthy"}

# 前端可访问
curl -I https://<CLOUDFRONT_域名>/
# 期望：HTTP 200
```

端到端冒烟：注册 → 登录 → 上传数据 → 启动分析 → 对话 → 生成报告 → 下载。

核对清单：

- [ ] ALB HTTPS 监听器使用有效 ACM 证书，HTTP 自动跳转 HTTPS。
- [ ] RDS 为 Multi-AZ、启用 KMS 加密与自动备份（保留 7 天）。
- [ ] ElastiCache 启用传输中加密（`rediss://`）与静态加密。
- [ ] S3 桶启用 KMS 加密、强制 SSL、阻止公共访问。
- [ ] CloudFront 最低协议 TLS 1.2，SPA 路由（403/404 → `index.html`）正常。
- [ ] ECS 任务角色具备 Bedrock / AgentCore / S3 / Secrets 权限。

---

## 7. 回滚与销毁

```bash
# 回滚：重新部署上一版本镜像或上一次 CDK 提交
cdk deploy --all -c region=us-east-1 -c certificate_arn=<arn>

# 销毁
cdk destroy --all -c region=us-east-1
```

> `RDS`、`S3 数据/报告桶`、`KMS 密钥` 的 `RemovalPolicy` 为 `RETAIN`，且 RDS 启用 `deletion_protection`，`cdk destroy` 不会删除这些资源，需手动清理，以防误删医学数据。前端桶为 `DESTROY`（含 `auto_delete_objects`）。

---

## 8. 故障排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `cdk deploy` 镜像构建失败 | 本地 Docker 未运行 / 未 `cdk bootstrap` | 启动 Docker；执行 `cdk bootstrap aws://<account>/us-east-1` |
| 部署报证书区域不匹配 | ACM 证书与 ALB 不同区域 | 使用 us-east-1 的证书 |
| ALB 监听器退回 HTTP | 未提供 `certificate_arn` | 部署时带上 `-c certificate_arn=<arn>` |
| ECS 任务反复重启 | 数据库 / Redis 连接失败 | 核对注入的 `APP_DB_*` / `APP_REDIS_URL`；确认迁移已执行 |
| Agent 调用失败 | `APP_AGENTCORE_RUNTIME_ARN` 未配置或模型未开通 | 回填 ARN 重部署 Compute；在 Bedrock 开通 Claude Sonnet |
| 前端刷新子路由 404 | CloudFront 错误响应未生效 | 确认 403/404 → `/index.html`（CdnStack 已内置） |
