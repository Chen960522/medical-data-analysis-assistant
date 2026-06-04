# 开源 MCP Server 集成配置

本文档说明「医析」Agent 集成的 **5 个开源 MCP Server** 的安装、启动与连通性验证方式。
图表生成、报告生成、CNKI 检索 3 个 **自研** MCP Server 不在本文档范围内。

> 需求追溯：3.1-3.5（数据分析）、10.9-10.21（PubMed 文献检索）、11.10-11.15（PDF 解析）

Agent 通过 stdio 协议拉起每个 MCP Server 子进程。启动命令/参数来源于
`app/core/config.py` 中的设置（可通过 `APP_MCP_*` 环境变量覆盖），由
`app/agent/agent.py` 的 `get_mcp_server_specs()` 解析为 `MCPServerSpec`。

## 服务器一览

| 名称 | 类型 | 安装 | stdio 启动 | 期望工具 |
|------|------|------|------------|----------|
| pubmed | pip | `pip install pubmed-mcp-server` | `python -m pubmed_mcp_server` | `search`、`get_article_details`、`search_by_mesh` |
| markitdown | pip | `pip install markitdown[all]` | `python -m markitdown.mcp_server` | `convert` |
| pandas | pip | `pip install pandas-mcp` | `python -m pandas_mcp` | `analyze_data`、`describe`、`query` |
| s3 | pip | `pip install awslabs-s3-mcp-server` | `python -m awslabs.s3_mcp_server` | `GetObject`、`PutObject`、`ListObjects` |
| postgres | npx | 无需 pip（运行时 `npx` 拉取） | `npx -y @modelcontextprotocol/server-postgres <连接串>` | `query` |

源仓库：

- pubmed：<https://github.com/JackKuo666/pubmed-mcp-server>
- markitdown：<https://github.com/microsoft/markitdown>
- pandas：<https://github.com/QuantGeekDev/pandas-mcp>
- s3：<https://github.com/awslabs/mcp>
- postgres：<https://github.com/modelcontextprotocol/servers>

## 一键安装（pip 服务器）

4 个 pip 安装的开源服务器已声明在 `backend/pyproject.toml` 的可选依赖组
`mcp-servers` 中，不会污染核心运行/测试依赖：

```bash
cd backend
pip install -e ".[mcp-servers]"
```

postgres-mcp-server 通过 `npx` 在运行时拉取，需本机安装 Node.js（>= 18）：

```bash
node --version   # 确认 >= 18，npx 随 Node 一起安装
```

## 各服务器配置说明

### 1. pubmed-mcp-server（PubMed 文献检索，需求 10.9-10.21）

```bash
pip install pubmed-mcp-server
```

- 启动：`python -m pubmed_mcp_server`
- 提供 PubMed 关键词检索、文献详情、MeSH 主题词检索（对应需求 10.14-10.21）。

### 2. MarkItDown MCP Server（PDF/文档解析，需求 11.10-11.15）

```bash
pip install markitdown[all]
```

- 启动：`python -m markitdown.mcp_server`
- `[all]` 额外组件用于解析 PDF/Word/Excel 等多种格式，将文档转为结构化 Markdown，
  供 Agent 直接利用 Claude 逐段翻译。

### 3. pandas-mcp（数据分析，需求 3.1-3.5）

```bash
pip install pandas-mcp
```

- 启动：`python -m pandas_mcp`
- 提供描述性统计、相关性、异常值、趋势、分组比较等分析能力。

### 4. aws-s3-mcp-server（S3 文件操作）

```bash
pip install awslabs-s3-mcp-server
```

- 启动：`python -m awslabs.s3_mcp_server`
- **AWS 凭证配置**：Agent 通过 `MCPServerSpec.env` 注入环境变量：
  - `AWS_REGION`：取自 `settings.bedrock_region`（默认 `us-west-2`）。
  - `AWS_ENDPOINT_URL` / `AWS_ENDPOINT_URL_S3`：当 `settings.s3_endpoint_url`
    被设置时注入（本地/开发场景指向 LocalStack，如 `http://localhost:4566`）。
  - `S3_BUCKET_NAME`：取自 `settings.s3_bucket_name`。
  - AWS Access Key/Secret 走标准 AWS 凭证链（环境变量、共享凭证文件或 ECS Task Role），
    生产环境推荐使用 IAM 角色，避免在配置中硬编码密钥。

### 5. postgres-mcp-server（只读 SQL 查询）

无需 pip 安装，运行时通过 `npx` 拉取：

```bash
npx -y @modelcontextprotocol/server-postgres "postgresql://user:pass@host:5432/dbname"
```

- 数据库连接串由 `get_mcp_server_specs()` 自动追加为最后一个参数（取自
  `settings.database_url`）。

## 验证 Agent 可调用所有开源工具

安装完依赖后，可用内置的连通性验证工具确认每个开源服务器都能启动并暴露其工具：

```bash
cd backend
pip install -e ".[mcp-servers]" strands-agents mcp
python -c "from app.agent import verify_all_open_source_servers; import json; print(json.dumps(verify_all_open_source_servers(), ensure_ascii=False, indent=2))"
```

返回结果为 `服务器名 -> [工具名列表]` 的映射；若某个服务器启动失败，则对应值为
`"error: <原因>"`，便于逐个排查。也可单独验证某个服务器：

```python
from app.agent import list_open_source_server_specs, verify_mcp_server_tools

specs = {s.name: s for s in list_open_source_server_specs()}
print(verify_mcp_server_tools(specs["pubmed"]))
```

> 说明：`strands` / `mcp` SDK 为延迟导入。未安装时，验证函数会抛出清晰的
> `RuntimeError`，提示安装 `strands-agents` 与 `mcp`。
