# FinLoop AI · Decision Studio

面向金融营销场景的可追溯决策工作台，重点展示 Agent 工作流、证据版本、可复现实验和失败恢复。FastAPI + SQLite + React + TypeScript，默认无密钥、离线可用。

这是可运行的实习作品集项目，不是投顾系统或生产营销平台。产品、客群和渠道结果均为虚构；规则通过率和模拟转化率不代表法律合规或真实业务收益。

## v0.2 的三个核心设计

### 决策证据护照

每次任务在**检索时**保存文档原文与 SHA-256 指纹，记录输入/上下文摘要、规则版本、随机种子和召回记忆 ID。历史结果分别核验“保存的快照是否完整”和“当前知识库是否已变化”。制度固定载入与查询命中明确区分，不把强制加入的制度算成检索效果。

### 同样本策略实验室

在同一组虚拟用户上比较清晰解释、证据优先和情景分析，使用相同送达/打开/响应随机数，控制模拟噪声。调整市场压力、触达疲劳与样本量，查看 Wilson 区间和配对差异区间。实验保存参数、假设和结果，**不写入策略权重或长期记忆**。

这是对人为设定概率的敏感性分析，不是从真实数据识别出的因果效果。配对区间采用正态近似，小差异样本时不稳健；无差异样本不代表真实效果完全一致。

### 可恢复、可复核的任务链

任务先落库再运行；相同幂等键与输入返回同一任务，输入冲突返回 409。单进程最多同时运行两项任务；失败或中断可按原输入重新尝试，每次尝试保留独立运行 ID 和阶段日志。只有唯一复核更新创意偏好权重，模拟结果不会自行“教会”策略。

## 功能地图

| 页面 | 可实际操作的功能 |
| --- | --- |
| 运行工作台 | 三种预设、指定策略/种子、后台运行、文案、规则、人工复核、证据护照、事件轨迹、JSON 导出 |
| 策略实验室 | 同样本比较、压力/疲劳参数、区间图、统计口径、历史实验 |
| 证据知识库 | 8 篇演示语料、中文二元词 + 段落 BM25、空结果、原文查看 |
| 记忆管理 | 内容去重、来源、类型筛选、禁用/恢复；同内容旧记录分组保留 |
| 质量评测 | 临时数据库中的 18 项回归、检索指标、负例、历史报告 |
| 运行历史 | 任务状态、失败重试、历次尝试日志、结果搜索与重新打开 |
| 运行配置 | 实际模型模式、执行器/预算/学习方式与能力边界 |

## 启动

要求 Python 3.11+、Node.js 22+。在仓库目录运行：

```bash
make install
make dev
```

开发界面：<http://localhost:5173>；接口文档：<http://127.0.0.1:8000/docs>。

只使用一个端口演示：

```bash
cd frontend
npm run build
cd ..
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。SQLite 位于 `data/finloop.db`，重启不会删除结果。

仓库提供 `docker compose up --build`，端口仅映射到本机，并使用命名数据卷。Docker 构建尚未在本轮本机验收；不要直接暴露公网。

## 演示路线（约 5 分钟）

1. 工作台选择“波动应对”，指定种子 42，创建任务。
2. 打开“证据护照”，查看原文、指纹和制度固定载入标记。
3. 打开“运行轨迹”，检查事件与模型调用状态。本地模式显示 `local-template`。
4. 实验室使用相同种子，改变压力假设，比较策略差异；说明结论依赖假设。
5. 禁用一条记忆，再次运行后检查护照的召回 ID，之后可恢复。
6. 运行隔离评测，确认不会增加业务运行或改变偏好权重。
7. 提交一次质量复核，观察入口锁定。网络重传不能重复更新权重。

## 验证

```bash
make test
make lint
make eval
cd frontend && npm run build
```

回归评测包含 3 个流程场景、10 个检索查询（含 2 个无关查询）、4 个对抗规则用例和 1 个脱敏预算用例。基线 **18/18**；8 个相关查询上 Recall@2 = 1.000、Precision@2 = 0.500、MRR@2 = 1.000。固定前 2 个位置为精确率分母；强制制度载入不参与检索评测。

这是 8 篇自建中文小语料的合成回归，不能证明真实金融检索性能。工程测试另覆盖并发去重、重复复核、失败重试、取消恢复、原子提交、记忆禁用、版本变化、模拟复现、数据隔离和模型降级。详见 [验证记录](docs/verification.md)。

## API 示例

推荐异步任务入口：

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-mission-2026-001' \
  -d '{"segment_id":"steady-planner","objective":"解释市场波动与配置纪律","market_signal":"市场波动放大，回撤咨询增加","seed":42,"variant":"clarity"}'
```

用返回的任务 ID 查询 `/api/jobs/{id}`，完成后用 `run_id` 打开结果。重发相同请求不会新增任务；新任务使用新幂等键。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST / GET | `/api/jobs` | 接收任务 / 最近 100 项任务 |
| GET | `/api/jobs/{id}` | 状态、事件与历次尝试 |
| POST | `/api/jobs/{id}/retry` | 仅失败/中断可完整重跑 |
| GET | `/api/runs/{id}` | 已保存结果 |
| GET | `/api/runs/{id}/evidence` | 快照与当前版本核验 |
| GET | `/api/runs/{id}/export` | 导出 JSON |
| POST / GET | `/api/experiments` | 执行 / 查阅实验 |
| GET / PATCH | `/api/memories` / `/api/memories/{id}` | 记忆分组 / 启用状态 |
| POST | `/api/feedback` | 唯一复核；兼容字段 converted 表示认可策略，不是真实转化 |
| POST / GET | `/api/evals/run` / `/api/evals/reports` | 隔离评测 / 报告 |

`POST /api/runs` 是同步兼容入口，不经过持久任务队列，客户端应优先使用 `/api/jobs`。执行只允许 `dry_run: true`。

## 接入模型

将 `.env.example` 复制为仓库根目录 `.env`，填写 FINLOOP_MODEL_PROVIDER、FINLOOP_MODEL_NAME、FINLOOP_API_KEY、FINLOOP_BASE_URL 后重启。环境变量优先于文件。

网关接受兼容 Chat Completions 的 JSON 输出接口。策略与内容可调用模型，其余仍是确定性规则/服务。无密钥时使用模板；服务异常、非 JSON 或字段校验失败会记录降级。真实模型质量、成本与服务商兼容性需要独立验收；本轮未使用付费远程模型。

## 工程边界

- 默认本机使用，无认证、租户权限、限流或分布式队列；不要用多 worker 部署任务执行器。
- 重启后已提交结果保留；未完成任务标记为中断，等待显式重试。不是节点级 checkpoint，不承诺外部副作用 exactly-once。
- SHA-256 用于一致性检查，不是防篡改签名。来源可追溯不等于逐句事实蕴含。
- 手机号、邮箱和 18 位身份证模式在输入落库前脱敏，备注也脱敏；正则并非完整 PII 检测器。不要输入真实客户资料。
- 规则是演示规则，不是正式金融合规引擎；洞察是关键词基线，检索没有 embedding 模型。
- 情景记忆来自模拟，客群知识来自目录规则，流程记忆来自固定政策；没有自主知识提炼。
- v0.1 历史保留；旧版模拟 bandit 权重不再使用，新权重存放在独立 review_arms。旧结果没有护照时，界面明确提示。

## 设计参考

借鉴显式工作流、长期记忆和消息事件设计，未引入以下框架作为运行依赖，不声称实现其完整能力：

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Microsoft AutoGen](https://github.com/microsoft/autogen)
- [LlamaIndex](https://github.com/run-llama/llama_index)

[架构取舍](docs/architecture.md) · [面试讲解](docs/interview-guide.md) · [验证记录](docs/verification.md)
