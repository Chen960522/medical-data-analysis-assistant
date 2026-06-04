# 部署文档 - 医学数据分析助手

本文档描述医学数据分析助手平台的本地开发环境搭建与 AWS 生产环境部署流程。

> 内容基于仓库实际代码（`infrastructure/` CDK 栈、`docker-compose.yml`、`backend/app/core/config.py`）整理。

## 目录

- [1. 系统架构概览](#1-系统架构概览)
- [2. 前置条件](#2-前置条件)
- [3. 本地开发环境部署](#3-本地开发环境部署)
- [4. 环境变量配置](#4-环境变量配置)
- [5. AWS 生产环境部署](#5-aws-生产环境部署)
- [6. AI Agent（Bedrock AgentCore）部署](#6-ai-agentbedrock-agentcore-部署)
- [7. MCP Server 部署](#7-mcp-server-部署)
- [8. 部署后验证](#8-部署后验证)
- [9. 回滚与销毁](#9-回滚与销毁)
- [10. 故障排查](#10-故障排查)

---

## 1. 系统架构概览

| 层级 | 技术 | 部署位置 |
|------|------|----------|
| 前端 | React 18 + TypeScript + Vite | S3 + CloudFront |
| 后端 API | Python FastAPI | ECS Fargate（2 vCPU / 4GB，2–10 实例自动扩缩） |
| 自研 MCP Server | 图表生成 / 报告生成 / CNKI 检索 | ECS Fargate（1 vCPU / 2GB，2–6 实例） |
| AI Agent | Strands Agents SDK + Claude Sonnet | Amazon Bedrock AgentCore Runtime |
| 关系数据库 | PostgreSQL 15 | RDS（db.r6g.large，Multi-AZ） |
| 缓存 | Redis 7 | ElastiCache（cache.r6g.large，集群模式） |
| 对象存储 | 数据文件 / 报告 / 前端静态资源 | S3（KMS 加密） |
| 加密 | AES-256 | KMS（自动轮换） |

CDK 栈依赖顺序：`Network → Security → Database / Storage / Compute → Cdn`

---

## 2. 前置条件

### 本地开发

- Node.js >= 18
- Python >= 3.11
- Docker & Docker Compose

### AWS 部署

- AWS 账号，具备创建 VPC、RDS、ElastiCache、ECS、S3、CloudFront、KMS 的权限
- AWS CLI v2，已通过 `aws configure` 配置凭证
- Node.js（用于 AWS CDK CLI）
- AWS CDK CLI：`npm install -g aws-cdk`
- 一张已验证的 ACM 证书（用于 ALB HTTPS 监听器，需位于 ALB 所在区域）
- 已在目标区域开通 Amazon Bedrock 的 Claude Sonnet 模型访问权限
- Docker（构建后端 / MCP 镜像并推送至 ECR）

---

## 3. 本地开发环境部署

### 3.1 启动基础设施服务

`docker-compose.yml` 提供本地 PostgreSQL、Redis、LocalStack（S3 + KMS）。

```bash
cd medical-data-analysis-assistant
docker compose up -d
```

启动后服务端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| postgres | 5432 | 用户 `postgres` / 密码 `postgres` / 库 `medical_analysis` |
| redis | 6379 | 无密码 |
| localstack | 4566 | 模拟 S3、KMS |

> 注意：Compose 中数据库名为 `medical_analysis`，而后端默认 `database_url` 指向 `medical_assistant`。请用环境变量覆盖（见 [第 4 节](#4-环境变量配置)）或在本地创建对应数据库以保持一致。

### 3.2 启动后端

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head        # 执行数据库迁移
uvicorn app.main:app --reload --port 8000
```

后端启动后：

- 健康检查：`GET http://localhost:8000/health` → `{"status": "healthy"}`
- API 文档：`http://localhost:8000/docs`
- 所有业务 API 挂载于 `/api/v1` 前缀下

### 3.3 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认开发地址 `http://localhost:5173`（Vite）。后端 CORS 当前允许 `http://localhost:3000`，若前端端口不同，请相应调整 `backend/app/main.py` 中的 `allow_origins` 或通过反向代理对齐。

### 3.4 运行测试

```bash
# 后端单元 + 属性测试
cd backend
python -m pytest tests/ -q

# 自研 MCP Server 测试
cd ../mcp-servers/report-generation && python -m pytest tests/ -q
cd ../cnki-search && python -m pytest tests/ -q
```

---

## 4. 环境变量配置

后端配置由 `backend/app/core/config.py`（pydantic-settings）管理。所有变量使用前缀 **`APP_`**，可通过环境变量或 `backend/.env` 文件提供。

### 4.1 关键变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `APP_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/medical_assistant` | PostgreSQL 连接串（本地用）。生产由下方分项自动拼装 |
| `APP_DB_HOST` | （空） | 数据库主机。**一旦设置,后端会用 HOST/PORT/NAME/USER/PASSWORD 拼装连接串**,无需 `APP_DATABASE_URL` |
| `APP_DB_PORT` | `5432` | 数据库端口 |
| `APP_DB_NAME` | （空） | 数据库名（生产为 `medical_analysis`） |
| `APP_DB_USER` | （空） | 数据库用户（生产由 Secrets Manager 注入） |
| `APP_DB_PASSWORD` | （空） | 数据库密码（生产由 Secrets Manager 注入） |
| `APP_REDIS_URL` | `redis://localhost:6379/0` | Redis 连接串（生产为 `rediss://`，启用 TLS） |
| `APP_JWT_SECRET_KEY` | `change-me-in-production-...` | 本地默认；生产由 Secrets Manager 注入 |
| `APP_JWT_ACCESS_TOKEN_EXPIRE_HOURS` | `24` | JWT 过期时间（小时） |
| `APP_BCRYPT_COST_FACTOR` | `12` | bcrypt 成本因子（>= 12） |
| `APP_MAX_LOGIN_ATTEMPTS` | `5` | 登录失败锁定阈值 |
| `APP_ACCOUNT_LOCKOUT_MINUTES` | `15` | 账户锁定时长 |
| `APP_S3_BUCKET_NAME` | `medical-data-files` | 数据文件 S3 桶名 |
| `APP_S3_ENDPOINT_URL` | `http://localhost:4566` | 本地 LocalStack；**生产环境留空以使用真实 S3** |
| `APP_AWS_REGION` | `us-east-1` | S3 所在区域 |
| `APP_S3_MAX_FILE_SIZE` | `104857600` | 数据文件上限 100MB |
| `APP_BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-20250514-v1:0` | Bedrock 模型 ID |
| `APP_BEDROCK_REGION` | `us-west-2` | Bedrock 区域 |
| `APP_AGENTCORE_RUNTIME_ARN` | （空） | 已部署的 AgentCore Runtime ARN，生产必填 |
| `APP_AGENTCORE_REGION` | `us-west-2` | AgentCore 区域 |

> **生产环境注入方式（由 CDK 自动配置）**：`ComputeStack` 已将上述变量写入 ECS 任务定义——
> - 普通配置（`APP_DB_HOST`/`APP_DB_PORT`/`APP_DB_NAME`/`APP_REDIS_URL`/`APP_S3_BUCKET_NAME`/`APP_BEDROCK_REGION`/`APP_AGENTCORE_*` 等）以 `environment` 注入；
> - 敏感值（`APP_DB_USER`、`APP_DB_PASSWORD` 来自 RDS 自动生成的 Secret；`APP_JWT_SECRET_KEY` 来自 `SecurityStack` 生成的 Secret）以 ECS `secrets` 从 Secrets Manager 注入,**不以明文出现在任务定义中**。
> - `APP_AGENTCORE_RUNTIME_ARN` 通过 `cdk deploy -c agentcore_runtime_arn=<arn>` 传入。
>
> 因此生产环境通常**无需手工维护 `.env`**；本地开发仍可使用下方示例。

### 4.2 生产环境 `.env` 示例

```bash
APP_DATABASE_URL=postgresql://dbadmin:<password>@<rds-endpoint>:5432/medical_analysis
APP_REDIS_URL=rediss://<elasticache-endpoint>:6379/0
APP_JWT_SECRET_KEY=<openssl rand -hex 32 生成的强随机值>
APP_S3_BUCKET_NAME=<DataFilesBucket 名称>
APP_S3_ENDPOINT_URL=
APP_AWS_REGION=us-west-2
APP_BEDROCK_REGION=us-west-2
APP_AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:<account>:runtime/medical-analysis
APP_AGENTCORE_REGION=us-west-2
```

> 生产环境敏感值（数据库密码、JWT 密钥）建议存放于 AWS Secrets Manager，并在 ECS 任务定义中以 `secrets` 注入，而非明文环境变量。RDS 凭证由 CDK 自动生成并存入 Secrets Manager（`rds.Credentials.from_generated_secret("dbadmin")`）。

---

## 5. AWS 生产环境部署

### 5.1 准备 CDK 环境

```bash
cd infrastructure
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

首次在账号/区域中使用 CDK 需执行引导：

```bash
cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
```

默认区域为 `us-west-2`（见 `app.py`），可通过 context 覆盖：`-c region=<region> -c account=<account>`。

### 5.2 容器镜像（由 CDK 自动构建）

`ComputeStack` 已配置为通过 CDK 资产（`ecs.ContainerImage.from_asset`）**自动构建并推送镜像到 ECR**，无需手动 `docker build` / `docker push`：

| 服务 | Dockerfile | 说明 |
|------|-----------|------|
| API 服务 | `backend/Dockerfile` | FastAPI + uvicorn，监听 8000，内置 `/health` 与 curl 健康检查 |
| MCP 服务 | `mcp-servers/Dockerfile` | 打包 3 个自研 MCP Server + 开源 MCP Server（含 WeasyPrint 原生依赖、Node.js 用于 `npx`） |

执行 `cdk deploy` 时，CDK 会在本地用 Docker 构建上述镜像、上传至 CDK 引导阶段创建的 ECR 资产仓库，并注入 ECS 任务定义。因此 **部署前需确保本地 Docker 守护进程在运行**。

> 注意事项：
> - `mcp-servers/Dockerfile` 中 `chart-generation` 目前仅有占位 `__init__.py`，尚未实现 server / `__main__`，故 `python -m mcp_servers.chart_generation` 暂不可启动,待图表生成 MCP 实现后即可用。
> - 开源 MCP Server 通过 pip 安装，若某个包暂不可用，镜像构建会打印 WARNING 但不中断（按需在 Dockerfile 调整为强制失败）。
> - 后端配置（数据库 / Redis / AgentCore / Bedrock 等）通过 `APP_*` 环境变量或 ECS Secrets 注入容器，建议在 `compute_stack.py` 的容器 `environment` / `secrets` 中补充（当前仅设置了 `ENV`、`PORT`）。

如需改用预构建镜像（在 CI 中构建并推送 ECR），可将 `from_asset(...)` 改回 `ecs.ContainerImage.from_ecr_repository(repo, tag)`。

### 5.3 部署基础设施

```bash
# 预览将创建的资源
cdk synth

# 部署全部栈（按依赖顺序）
cdk deploy --all \
  -c certificate_arn=arn:aws:acm:us-west-2:<account>:certificate/<id> \
  -c agentcore_runtime_arn=arn:aws:bedrock-agentcore:us-west-2:<account>:runtime/medical-analysis
```

> `certificate_arn` 用于 ALB 的 HTTPS（TLS 1.2+）监听器。未提供时 ALB 会退回 HTTP（仅供 synth/本地验证，**生产必须提供证书**）。
>
> `agentcore_runtime_arn` 会注入到 API 容器的 `APP_AGENTCORE_RUNTIME_ARN`。可在首次部署基础设施时留空，待 [第 6 节](#6-ai-agentbedrock-agentcore-部署) 部署 AgentCore 后再带上该参数重新 `cdk deploy MedicalAnalysis-Compute`。

也可单独部署某个栈：

```bash
cdk deploy MedicalAnalysis-Network
cdk deploy MedicalAnalysis-Database
```

栈清单：

| 栈名 | 资源 |
|------|------|
| `MedicalAnalysis-Network` | VPC（10.0.0.0/16）、3 层子网、NAT、VPC Endpoints（S3/ECR/CloudWatch/Bedrock） |
| `MedicalAnalysis-Security` | KMS 主加密密钥（自动轮换） |
| `MedicalAnalysis-Database` | RDS PostgreSQL 15（Multi-AZ）、ElastiCache Redis 7 |
| `MedicalAnalysis-Storage` | S3 数据桶、报告桶（KMS 加密、强制 SSL、版本化、生命周期） |
| `MedicalAnalysis-Compute` | ECS Fargate 集群、ALB、API 服务、MCP 服务 |
| `MedicalAnalysis-Cdn` | 前端 S3 桶 + CloudFront 分发 |

### 5.4 数据库迁移

基础设施部署完成后，针对 RDS 执行 Alembic 迁移（从能访问私有数据子网的环境运行，如堡垒机或一次性 ECS 任务）：

```bash
APP_DATABASE_URL=postgresql://dbadmin:<password>@<rds-endpoint>:5432/medical_analysis \
  alembic upgrade head
```

### 5.5 部署前端静态资源

```bash
cd frontend
npm install
npm run build                       # 产物输出至 dist/

aws s3 sync dist/ s3://<FrontendStaticBucket 名称>/ --delete

# 使 CloudFront 缓存失效
aws cloudfront create-invalidation \
  --distribution-id <DistributionId> \
  --paths "/*"
```

桶名与分发 ID 可从 `cdk deploy` 输出或 CloudFormation 控制台获取。

---

## 6. AI Agent（Bedrock AgentCore）部署

Agent 入口为 `backend/app/agent/entrypoint.py` 中的 `handle_invocation`，通过 `bedrock-agentcore` SDK 部署。

```bash
cd backend
pip install bedrock-agentcore-starter-toolkit

# 配置部署入口
agentcore configure --entrypoint app/agent/entrypoint.py --non-interactive

# 部署到 AgentCore Runtime
agentcore deploy
```

部署完成后，将返回的 Runtime ARN 配置到后端环境变量 `APP_AGENTCORE_RUNTIME_ARN`，并确保：

- 目标区域（`APP_AGENTCORE_REGION`，默认 `us-west-2`）已开通 Claude Sonnet 模型访问。
- ECS 任务角色具备调用 `bedrock-agentcore` 与 `bedrock:InvokeModel` 的 IAM 权限。

---

## 7. MCP Server 部署

| MCP Server | 类型 | 部署方式 |
|------------|------|----------|
| 图表生成 / 报告生成 / CNKI 检索 | 自研 | 打包进 MCP 容器镜像，部署于 ECS Fargate MCP 服务 |
| pubmed-mcp-server | 开源 | `pip install pubmed-mcp-server`，stdio 启动 |
| MarkItDown | 开源 | `pip install 'markitdown[all]'`，stdio 启动 |
| pandas-mcp | 开源 | `pip install pandas-mcp`，stdio 启动 |
| aws-s3-mcp-server | 开源 | `pip install awslabs-s3-mcp-server`，需 AWS 凭证 |
| postgres-mcp-server | 开源 | `npx -y @modelcontextprotocol/server-postgres <连接串>` |

各 MCP Server 的启动命令由后端配置项 `APP_MCP_*_COMMAND` / `APP_MCP_*_ARGS` 控制（见 `config.py`），可按环境覆盖。开源 Server 需在 MCP 容器镜像中预装上述依赖（Python 包 + Node.js 用于 `npx`）。

---

## 8. 部署后验证

```bash
# 1. API 健康检查（经 ALB）
curl https://<alb-或域名>/health
# 期望：{"status": "healthy"}

# 2. 前端可访问
curl -I https://<cloudfront-域名>/
# 期望：HTTP 200，返回 index.html

# 3. 端到端冒烟
#    注册 → 登录 → 上传数据 → 启动分析 → 对话 → 生成报告 → 下载
```

核对清单：

- [ ] ALB HTTPS 监听器使用有效 ACM 证书，HTTP 自动跳转 HTTPS
- [ ] RDS 为 Multi-AZ、已启用 KMS 加密与自动备份（保留 7 天）
- [ ] ElastiCache 已启用传输中加密（`rediss://`）与静态加密
- [ ] S3 桶启用 KMS 加密、强制 SSL、阻止公共访问
- [ ] CloudFront 最低协议 TLS 1.2，SPA 路由（403/404 → index.html）正常
- [ ] `APP_JWT_SECRET_KEY` 已替换为强随机值
- [ ] ECS 任务角色具备 Bedrock / AgentCore / S3 / Secrets 权限

---

## 9. 回滚与销毁

```bash
# 回滚：重新部署上一版镜像 tag 或上一次 CDK 提交
cdk deploy --all -c certificate_arn=<arn>

# 销毁（谨慎！）
cdk destroy --all
```

> 重要：`RDS`、`S3 数据/报告桶`、`KMS 密钥` 的 `RemovalPolicy` 均为 `RETAIN`，且 RDS 启用了 `deletion_protection`。`cdk destroy` **不会**删除这些资源，需手动清理，以防误删医学数据。前端桶 `RemovalPolicy` 为 `DESTROY`（含 `auto_delete_objects`）。

---

## 10. 故障排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 后端启动报数据库连接失败 | `APP_DATABASE_URL` 库名与实际不符（`medical_assistant` vs `medical_analysis`） | 统一库名或覆盖环境变量 |
| 本地 S3 操作失败 | LocalStack 未启动或 `APP_S3_ENDPOINT_URL` 配置错误 | `docker compose up -d`；确认指向 `http://localhost:4566` |
| ALB 部署回退为 HTTP | 未提供 `certificate_arn` context | `cdk deploy -c certificate_arn=<arn>` |
| ECS 任务无法拉取镜像 | CDK 资产构建失败或本地 Docker 未运行 | 确保部署机已启动 Docker；检查 `cdk deploy` 的镜像构建日志 |
| Agent 调用失败 | `APP_AGENTCORE_RUNTIME_ARN` 未配置或 Bedrock 未开通模型 | 配置 ARN；在 Bedrock 控制台开通 Claude Sonnet |
| 前端刷新子路由 404 | CloudFront 错误响应未配置 | 确认 403/404 → `/index.html`（CdnStack 已内置） |
| 登录被锁定 | 连续失败 >= 5 次 | 等待 15 分钟或调整 `APP_ACCOUNT_LOCKOUT_MINUTES` |

---

## 附录：常用命令速查

```bash
# 本地：一键起依赖
docker compose up -d

# 后端
uvicorn app.main:app --reload --port 8000
alembic upgrade head
python -m pytest tests/ -q

# 前端
npm run dev
npm run build

# CDK
cdk synth
cdk deploy --all -c certificate_arn=<arn>
cdk destroy --all

# 前端发布
aws s3 sync dist/ s3://<bucket>/ --delete
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```
