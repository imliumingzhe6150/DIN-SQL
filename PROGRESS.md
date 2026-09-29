# DIN-SQL 项目进度

更新时间：2026-09-29

## 项目目标

完成一次入门级 DIN-SQL 实践，随后进入 MAC-SQL。以下三个标准是本项目的最终结束标准，不再增加额外毕业任务。

## 已完成

- [x] 理解主循环和 Schema Linking。
- [x] 准备 Spider 数据，理解 `tables.json`。
- [x] 手写并运行 prompt inspection。
- [x] 接入 DeepSeek API。
- [x] 实现四阶段单题流程：Schema Linking → Classification / Decomposition → SQL Generation → Self-Correction。
- [x] 实现 EASY、NON-NESTED、NESTED 三个生成分支及子问题解析。
- [x] 在 SQLite 中执行生成和修正后的 SQL，并与 Gold 查询结果比较。
- [x] 支持 `--index` 选题，保存单题结果 JSON。
- [x] 运行 EASY 案例；运行并保存 NESTED 样本 12。

样本 12 的生成、修正后 SQL 已核对，执行结果与 Gold 一致。NON-NESTED 分支已实现，其运行验证可以放在下面的 30 道实验中完成。

## 剩余三个结束标准

### 1. 三种 label 各跑 10 道

- [ ] 挑选 30 道不同的问题：EASY 10 道、NON-NESTED 10 道、NESTED 10 道。
- [ ] 做最小批量入口，先循环运行这 30 道题的 DIN-SQL 流程并保存结果。
- [ ] 个别题失败时记录错误，继续剩余题目；不为凑准确率替换失败题。
- [ ] 确认三类各 10 道都已尝试，汇总 DIN-SQL 结果。

类别按题目所需的 SQL 结构预先确定：无 JOIN、无嵌套为 EASY；需要 JOIN、无嵌套为 NON-NESTED；需要嵌套或集合运算为 NESTED。模型预测类别另行记录，预测错误不改变原来的样本分组。这里不是 Spider 官方难度标签，也不是把同一道题重复运行 10 次。

结果匹配使用本地 SQLite 比较即可；出现不匹配时人工核对。无需接入官方完整评测。

### 2. 做一次 baseline 对比

- [ ] 实现 Baseline：问题 + Schema（表、字段、外键）→ 直接生成 SQL。
- [ ] 用相同 DeepSeek 模型、同一批题，运行 Baseline 与现有 DIN-SQL 四阶段流程。
- [ ] 保存两种方法的 SQL、执行是否成功、结果是否与 Gold 匹配。
- [ ] 汇总两种方法在这批题上的执行成功率和结果匹配率，写几句话说明比较结果。

Baseline 直接使用第 1 项选定的 30 道题，不另选样本。输入只有原问题和 Schema，不使用 DIN-SQL 的 Schema Links、分类、子问题或 SQL。比较查询结果，不以 SQL 文本是否完全相同判定正确；没有排序要求时忽略行顺序、保留重复行。

### 3. 错误分析：有错误才写

- [ ] 检查实验中出现的错误，包括 SQL 执行失败、结果错误、分类或输出解析错误。
- [ ] 如果有错误，在 `error_analysis.md` 简要记录出错题目、模型 SQL、最早出错的阶段及原因。
- [ ] 如果没有错误，在本文件注明“本批样本未发现错误”，无需创建错误分析文件。

不要求凑够 10 个错误案例；相同原因的错误可以合并说明。

## 下一步

先挑选三类各 10 道题，用简单循环批量运行 DIN-SQL；再写最小 baseline 函数，运行同一批题并比较结果；最后有错误就简要分析，没有错误就记录无错误。三个标准完成后进入 MAC-SQL。

当前 baseline 和批量脚本尚未实现；之前新增的脚本已按要求撤回。

## 完成判定

- [ ] EASY、NON-NESTED、NESTED 各 10 道完成 DIN-SQL 运行尝试并保存结果。
- [ ] 完成同一批题上的 Baseline 与 DIN-SQL 对比。
- [ ] 有错误时完成简要分析；无错误时注明本批未发现错误。

不要求 DIN-SQL 胜过 baseline。上述三项完成即结束本项目，不再要求额外架构文档、脱离代码重写、Token/费用统计、复杂容错或完整 dev 集实验。
