# Agent 使用指南

本项目是一套供 AI Agent 调用的本地工具包，不是单一 Skill，也不是自动投资顾问。它包含说明、两阶段工作流、CLI、脚本、测试、质量守卫和输出模板。

## Agent 的输入

用户至少应提供：

- 本项目的本地绝对路径；
- 一只股票代码或包含 `company_code` 的 CSV；
- 使用内置概念库还是用户自己的冻结概念库；
- 输出目录；
- 可选的数据截止期 `YYYYQ1`、`YYYYH1`、`YYYYQ3` 或 `YYYYA`。

## Agent 执行协议

1. 阅读 `README.md`、本文件和 `docs/WORKFLOWS.md`。
2. 确认 Python 3.11+，安装 `pip install -e '.[dev]'`。
3. 运行 `python scripts/check_public_repo.py` 和必要测试。
4. 确认概念库顶层 `status` 为 `frozen`，不得跳过概念审核门禁。
5. 单股使用 `concept-screener screen-company`；批量使用 `concept-screener screen-batch --resume`。
6. 检查每家公司的 `pipeline_manifest.json`，失败项必须定位、修复或明确报告。
7. 检查 `deliverables/03_final_assessment.json` 的资料状态，不能把 `partial_data`、`data_incomplete` 或 `evidence_limited` 写成完整结论。
8. 从 `02_evidence_sentences.csv` 抽样核对 PDF 页码和上下文。
9. 汇总指标覆盖、概念评分、反证、CANSLIM 辅助状态和外部数据缺失。
10. 明确声明结果不构成投资建议，不输出确定性收益预测或“必买/必卖”结论。

## 推荐给 Agent 的任务模板

```text
请阅读并使用本地工具包：<项目绝对路径>

待筛选公司列表：<CSV绝对路径>
冻结概念库：<concepts.json绝对路径>
输出目录：<输出绝对路径>
数据截止期：<可选>

请按 AGENT_GUIDE.md 和 docs/WORKFLOWS.md 执行：
1. 检查环境和概念库；
2. 运行批量筛选并允许失败后重试；
3. 检查所有 pipeline_manifest；
4. 抽样核对原文证据；
5. 汇总概念分数、指标覆盖、风险反证、CANSLIM 辅助状态和资料限制；
6. 不得把量化分数写成投资建议。
```

## 概念库更新

只有用户明确要求更新研究框架时，Agent 才应运行阶段一：

```bash
concept-screener prepare-concepts \
  --input-dir /path/to/private-notes \
  --workspace-dir concept_workspace/my-research
```

原始论坛发言、研究笔记和中间洞察可能涉及版权或隐私，必须留在 `.gitignore` 排除的本地工作区。Agent 不得自动把它们提交到 GitHub。

## 不允许的行为

- 不得伪造缺失指标、证据、行情或机构持仓。
- 不得绕过失败守卫或把失败清单删除后声称成功。
- 不得把关键词命中直接解释为公司事实。
- 不得提交 API Key、Cookie、券商会话、持仓、自选股或私人语料。
- 不得在用户未授权时修改冻结概念库和评分规则。
