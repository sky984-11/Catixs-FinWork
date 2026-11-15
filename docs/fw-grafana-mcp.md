# FW 助手 Grafana MCP

沿用 `POST /api/v1/fw-assistant/chat`，无需新增前端接口或改变响应结构。助手新增 `grafana_tools`（发现工具和 inputSchema）与 `grafana_read`（按定义查询），查询来源在 `data.db.queries` 中标记为 `grafana_read`，结果包含 `source: Grafana MCP`、`truncated`、`result`。未调用时不启动外部进程。

后端运行环境须安装 uv/uvx，首次启动下载官方 `mcp-grafana==2.2.0`。生产环境可预先执行 `uvx mcp-grafana==2.2.0 --version` 预热缓存。配置：

- `FW_ASSISTANT_GRAFANA_ENABLED=true`：功能开关；false 不提供工具且拒绝调用。
- `GRAFANA_MCP_COMMAND=uvx`：uvx 可执行文件名称或绝对路径（不是任意 shell 命令）。
- 复用 `GRAFANA_URL`、`GRAFANA_API_TOKEN`，仅作为官方进程的 `GRAFANA_URL`、`GRAFANA_SERVICE_ACCOUNT_TOKEN` 环境变量传入，不传给模型。

采用官方 STDIO 传输、`--disable-write` 和关闭匿名使用统计；平台额外使用固定只读工具白名单。支持数据源发现、仪表盘搜索/摘要/属性/面板查询定义、Prometheus 查询和指标/标签发现、Loki 查询/标签发现。不开放任意 API、原始 SQL、仪表盘修改、告警配置修改。Zabbix、PostgreSQL、Akvorado 数据源可发现，但不能据此宣称它们支持 PromQL 或任意查询。

权限：当前用户必须启用且拥有现有 `GET /api/v1/pve/grafana/proxy/{path}` 权限，或按项目现有规则为管理员/超级管理员。发现及执行都检查权限。授权意味着允许读取 Grafana 服务账号可见的监控数据，不按 FinWork 项目/客户行级范围进一步过滤；请仅向合适的运维角色开放该权限。

调用运行在线程中，兼容 Windows 后端事件循环；每次 MCP 会话约 20 秒超时，结束时清理自身进程树。单条协议消息上限 4 MiB，模型结果截断至 20000 字符并明确标记；沿用助手 8 次工具调用、60 秒整轮时限和结果预算。取消请求后后台线程仍会在会话时限内结束。上游失败作为 `isError=true` 工具结果，返回脱敏错误，助手数据库工具仍可使用。聊天端点认证和原 HTTP 错误约定不变。

示例问题：“Grafana 有哪些数据源？”、“搜索 PVE 相关仪表盘”、“查询 Prometheus 过去 30 分钟的 up 指标，并说明数据源和时间范围”。优先缩小指标与时间范围，不编造 UID、查询结果或把被截断结果当作完整数据。

验证：`python -m unittest tests.test_fw_grafana_mcp tests.test_fw_database_mcp tests.test_fw_ops_mcp`。

依据：[Grafana 官方 MCP 文档](https://github.com/grafana/mcp-grafana)，其中说明 `uvx` 启动、凭据环境变量和 `--disable-write` 模式。
