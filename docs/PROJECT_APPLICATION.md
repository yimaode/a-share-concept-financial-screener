# 项目介绍与 API 额度使用说明

## 一句话项目说明（英文）

> A-Share Investment Concept Financial Screener solves the problem of turning scattered investment research, forum insights, and personal screening methods into repeatable, auditable financial-report screening workflows for individual investors, independent researchers, and AI-agent users. It is currently pre-launch, with 0 GitHub stars, 0 public downloads, and 0 known public users, and is actively maintained through automated regression testing today, with regular releases, issue triage, and pull request reviews planned after launch. It is important because it makes personalized, evidence-linked stock screening more accessible to non-programmers and gives the open-source agent ecosystem a reusable toolkit instead of a closed stock-recommendation service.

## 一句话项目说明（中文）

> “基于投资概念固化的 A 股财报量化筛选器”帮助个人投资者、独立研究者和 AI Agent 用户，把零散的论坛观点、研究笔记和个人选股方法转化为可重复、可审计的财报筛选流程。项目目前尚未正式发布，因此现阶段为 0 GitHub stars、0 次公开下载和 0 名已知公开用户；当前通过自动化回归测试持续维护，并计划在发布后通过定期版本、Issue 分类处理和 Pull Request 审查长期迭代。它的价值在于降低非程序员建立个性化、证据可回溯股票筛选流程的门槛，并为开源 Agent 社区提供一套可复用的本地工具包，而不是一个封闭的荐股服务。

## 项目背景说明

这是一个以欧奈尔 CANSLIM 思路为辅助框架、以“投资概念固化”为核心的 AI Agent 股票筛选工具包。用户可以向 Agent 提供公司列表、冻结概念库和工具的本地路径，让 Agent 根据项目说明自动完成财报获取、指标整理、财报原文证据抽取、概念量化评分、风险提示和初步研究候选排序。

工具包含两个相对独立的环节：

1. **概念固化**：处理用户有权使用的论坛发言、研究笔记或投资方法，形成概念库，并为概念指定需要验证的关键财务指标和财报证据，例如 EPS/利润增长、收入增长、毛利率、研发费用率、合同负债和风险关键词。
2. **自动筛选工具包**：使用冻结概念库重复处理一只或一批公司，输出指标、趋势、证据、评分、资料状态和 CANSLIM 辅助评估。

这套工具不是一个单独的 Skill，而是包含 Agent 阅读说明、工作流程、自动化命令、Python 脚本、质量守卫、测试和结果输出模板的完整 Agent 工具包。

项目作者并非计算机专业，也没有传统代码开发背景。项目是在短时间内通过 Codex 持续创建、测试、修改和迭代形成的，并已实际用于减轻公司初筛和财报整理的工作量。开源项目的目标是分享这一工作方式、持续改进工具，并帮助有类似研究需求但缺少编程背景的股票筛选者降低重复劳动。

## 您将如何使用 API 额度来开展项目（精简版）

> API 额度将用于持续维护和改进当前的开源筛选工具，包括复现 Issue、审查代码、补充自动化测试、改进 Agent 使用说明和验证发布版本；同时用于开发跨市场数据源切换层（A 股、美股和港股）、本地财报 PDF OCR 路由，以及更可靠的本地财报表格和指标抽取。当前系统主要采用“联网财务数据 + 本地 PDF 关键词/证据句”的混合方案，因为复杂、跨页财务表格的全本地自动识别仍不够稳定。额度将帮助项目逐步实现可验证的 OCR、表格结构恢复、单位与负号校验、在线数据对账和人工复核队列，而不会被用于生成确定性荐股、收益承诺或绕过数据源授权。

## 您将如何使用 API 额度来开展项目（详细版）

API 额度计划用于以下方向：

1. **持续维护与质量保障**
   - 协助定位和复现公开 Issue；
   - 审查修改范围并生成边界测试、失败测试和回归测试；
   - 维护 Agent 指南、README、版本说明和迁移文档；
   - 检查数据缺失、接口改版、PDF 解析异常和评分规则回归；
   - 支持定期版本发布、Issue 分类和 Pull Request 审查。

2. **跨市场数据源切换包**
   - 为 A 股、美股和港股建立统一的公司、报告期、财务指标和行情数据接口；
   - 支持按市场切换公开或用户授权的数据源；
   - 增加字段映射、单位换算、币种、复权、速率限制、缓存和数据溯源；
   - 当某一数据源失效时提供明确降级和替代路径，而不是伪造结果。

3. **本地财报 PDF OCR 抽取器**
   - 自动判断 PDF 是文本型、扫描型、混合型还是损坏文件；
   - 对代表性页面进行渲染、OCR 和视觉核对；
   - 保存页码、方法、置信度、失败原因和重试记录；
   - 优先使用本地、轻量工具，避免不必要地上传私人文档。

4. **完善本地财报表格与指标抽取**
   - 改进跨页表格、合并单元格、表头层级和单位识别；
   - 检查负号、百分号、千位分隔符、币种和累计/单季口径；
   - 将本地 PDF 抽取结果与联网财务数据进行对账；
   - 为冲突、低置信度或无法自动判断的数据建立人工复核队列；
   - 在验证可靠之前，继续保留当前“联网数据取值 + 本地 PDF 原文证据”的稳健方案。

5. **Agent 使用体验**
   - 改进可让 Agent 直接阅读的任务协议、失败恢复策略和结果模板；
   - 降低非程序员配置和运行批量筛选的门槛；
   - 减少重复提示和不必要的 Token 消耗，让确定性脚本完成适合自动化的部分。

API 额度不会用于绕过第三方授权、存储用户券商凭证、生成确定性买卖结论或承诺投资收益。测试优先使用合成数据和允许公开使用的聚合样本。
