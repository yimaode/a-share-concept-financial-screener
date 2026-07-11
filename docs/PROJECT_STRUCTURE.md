# 项目结构

| 路径 | 是否适合提交 | 说明 |
| --- | --- | --- |
| `config/concepts.json` | 是 | 脱敏后的内置冻结概念库 |
| `docs/` | 是 | 工作流、结构和展示图片 |
| `examples/` | 是 | 合成笔记、公开股票代码和聚合示例 |
| `scripts/` | 是 | 可复现维护脚本 |
| `src/` | 是 | 核心代码 |
| `tests/` | 是 | 自动测试和合成夹具 |
| `AGENT_GUIDE.md` | 是 | Agent 自动调用协议和任务模板 |
| `concept_workspace/` | 否 | 可能包含私有原文和中间洞察 |
| `data/raw_pdfs/` | 否 | 下载的第三方财报副本 |
| `outputs/` | 否 | 每次运行的完整结果和证据原文 |
| `inputs/` | 否 | 用户自己的股票清单、自选股或持仓 |
| `.env*`、`credentials/` | 否 | 凭证和本地配置 |

## 核心包

- `concept_builder/`：阶段一的切片、洞察、候选、审核和冻结。
- `data_fetcher/`：公开财务报告、财务指标、行情和机构数据。
- `pdf_extractor/`：PDF 文本与页码清单。
- `evidence_extractor/`：固定概念的正负证据句。
- `metric_trends/`：同比、环比、百分点变化和 CAGR。
- `concept_scores/`：概念评分、覆盖率和资料状态。
- `canslim/`：C/A/N/S/L/I/M 七维评估。
- `reporting/`：单股、批量主管线和最终交付物。

Python 包目录 `ds_finance_concept` 为兼容早期版本保留；面向用户的发行包和主命令分别是 `a-share-concept-financial-screener` 与 `concept-screener`。`canslim-screener` 仅作为兼容别名保留。
