# GitHub 发布建议

## 仓库名称

推荐：`a-share-concept-financial-screener`

备选：`investment-concept-screener`、`concept-driven-a-share-screener`

## GitHub About 描述

> 将研究笔记固化为投资概念库，并由 AI Agent 自动完成 A 股财务指标、财报证据、量化评分、风险提示与 CANSLIM 辅助评估。

## Topics

```text
a-share
stock-screener
financial-analysis
investment-research
investment-concepts
ai-agent
canslim
python
pdf-extraction
quantitative-analysis
```

## 首个 Release

- Tag：`v0.1.0`
- 标题：`v0.1.0 — 概念固化与 A 股财报量化筛选基础版`
- 重点：两阶段工作流、Agent 指南、单股/批量筛选、证据页码、资料状态、CANSLIM 辅助模块、公开仓库安全扫描。

## 发布前检查

```bash
python scripts/check_public_repo.py
python -m pytest -q
python -m pip wheel . --no-deps --wheel-dir dist
git status --short
```

还应人工确认：

- README 图片在 GitHub 正常显示；
- `config/concepts.json` 不含私人 `source_quote_ids`；
- 没有 `.env`、Cookie、券商凭证、持仓、自选股、私人笔记、原始财报或历史输出；
- GitHub Security 的 private vulnerability reporting 已启用；
- Repository Topics、MIT License 和 About 描述已经设置；
- 首次提交和 Release 没有包含 `dist/`、缓存或本地虚拟环境。
