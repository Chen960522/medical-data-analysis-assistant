# 医学数据分析助手 (Medical Data Analysis Assistant)

智能医学数据分析平台，面向医学研究人员和临床工作者，提供数据上传、AI 多维度分析、可视化图表生成、分析报告导出、对话式交互分析、文献检索与翻译等核心功能。

## 项目结构

```
medical-data-analysis-assistant/
├── frontend/              # React 18 + TypeScript + Vite 前端应用
│   ├── src/               # 源代码
│   ├── package.json       # 依赖配置
│   ├── vite.config.ts     # Vite 构建配置
│   └── tsconfig.json      # TypeScript 配置
├── backend/               # Python FastAPI 后端服务
│   ├── app/               # 应用代码
│   │   └── main.py        # FastAPI 入口
│   ├── alembic/           # 数据库迁移
│   ├── tests/             # 测试
│   ├── pyproject.toml     # Python 项目配置
│   └── alembic.ini        # Alembic 配置
├── infrastructure/        # AWS CDK 基础设施代码
│   ├── app.py             # CDK 应用入口
│   ├── cdk.json           # CDK 配置
│   └── requirements.txt   # CDK 依赖
├── mcp-servers/           # 自研 MCP Server
│   ├── chart-generation/  # 图表生成 MCP Server
│   ├── report-generation/ # 报告生成 MCP Server
│   └── cnki-search/       # CNKI 文献检索 MCP Server
├── docs/                  # 项目文档
├── docker-compose.yml     # 本地开发环境
└── README.md              # 本文件
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite, Ant Design 5, ECharts 5, Zustand |
| 后端 | Python FastAPI, SQLAlchemy, Alembic, Pydantic |
| AI | Strands Agents SDK, Amazon Bedrock (Claude Sonnet), MCP |
| 数据库 | PostgreSQL 15, Redis 7 |
| 基础设施 | AWS CDK (Python), ECS Fargate, S3, RDS, ElastiCache |
| 本地开发 | Docker Compose (PostgreSQL, Redis, LocalStack) |

## 快速开始

### 前置条件

- Node.js >= 18
- Python >= 3.11
- Docker & Docker Compose

### 启动本地开发环境

```bash
# 启动基础设施服务（PostgreSQL、Redis、LocalStack）
docker compose up -d

# 启动后端
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 启动前端
cd frontend
npm install
npm run dev
```

### 数据库迁移

```bash
cd backend
alembic upgrade head
```

### CDK 部署

```bash
cd infrastructure
pip install -r requirements.txt
cdk synth
cdk deploy
```

## 开发规范

- 前端代码使用 ESLint 进行代码检查
- 后端代码使用 Ruff 进行代码检查和格式化
- 使用 Hypothesis 进行属性测试
- 所有 API 端点需要认证（除 health check）
