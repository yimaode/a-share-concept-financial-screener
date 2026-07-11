# 两阶段工作流

## 阶段一：概念准备与冻结

这一阶段用于低频更新研究框架。输入可以是用户自己拥有版权或使用权的 Markdown 笔记。

```bash
concept-screener prepare-concepts \
  --input-dir /path/to/private-notes \
  --workspace-dir concept_workspace/my-research
```

工作区依次包含：

1. `01_quote_cards.jsonl`：保持出处和行号的原文切片；
2. `02_insight_cards.jsonl`：规则化投资主张、信号和可能指标；
3. `03_concept_candidates.json`：合并后的候选概念；
4. `03_concept_candidates_review.md`：候选审核清单；
5. `04_concepts.draft.json/yaml`：待审核概念草稿；
6. `04_concepts_review.md`：人工审核入口。

这些文件可能包含原文，不应提交 Git。审核者需要确认定义、正负关键词、硬指标、证据数量和误判风险，并将允许冻结的概念标为 `approved`。

校验和冻结是独立门禁：

```bash
concept-screener validate-concepts \
  --concepts-json concept_workspace/my-research/04_concepts.draft.json \
  --output-report concept_workspace/my-research/validation.md

concept-screener freeze-concepts \
  --concepts-json concept_workspace/my-research/04_concepts.draft.json \
  --output-json config/my-concepts.json \
  --output-yaml concept_workspace/my-research/my-concepts.yaml
```

阶段一不会下载财报或筛选公司。

## 阶段二：按冻结概念抽取与筛选

阶段二只接受 `status: frozen` 的概念库。单股入口：

```bash
concept-screener screen-company \
  --company-code 300750 \
  --concepts-file config/my-concepts.json \
  --output-dir outputs/300750
```

批量入口：

```bash
concept-screener screen-batch \
  --companies-file examples/companies.csv \
  --concepts-file config/my-concepts.json \
  --output-dir outputs/batch \
  --resume
```

主管线阶段包括报告下载、PDF 文本抽取、财务指标、趋势、行情特征、证据、概念评分、风险分析、CANSLIM 辅助评估和最终交付物。每个阶段记录在 `pipeline_manifest.json`。

## 为什么拆分

- 概念库是研究假设，应该经过人工审核并版本化。
- 公司数据是重复运行对象，不应每次重新处理原始笔记。
- 私有语料不进入公司结果，降低版权、隐私和泄漏风险。
- 确定性规则默认无需 LLM Token，便于复现和批量运行。
- 概念库升级和数据管线升级可以独立测试、回滚和维护。
