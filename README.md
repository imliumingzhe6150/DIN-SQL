# DIN-SQL 入门实践

本实验比较基于 DIN-SQL 四阶段思路的简化实现与直接生成 SQL 的 baseline，均使用相同 DeepSeek 模型。

简化实现包含 Schema Linking → Classification / Decomposition → SQL Generation → Self-Correction 四个阶段；baseline 仅使用问题和数据库 Schema（表、字段、外键）直接生成 SQL。

## 实验样本与评测

从 Spider dev 集选取 30 道不同问题，按 Gold SQL 结构预先分为三组，每组 10 道：

- EASY：无 JOIN、无嵌套。
- NON-NESTED：需要 JOIN、无嵌套。
- NESTED：需要嵌套或集合运算。

分组不是 Spider 官方难度标签，也不随模型预测类别改变。两种方法使用相同的 30 道题，在本地 SQLite 中执行 SQL 并与 Gold 查询结果比较。无排序要求时忽略行顺序，保留重复行。

## 实验结果

| 方法                       | 执行成功率    | EASY 结果匹配 | NON-NESTED 结果匹配 | NESTED 结果匹配 | 总结果匹配率   |
| -------------------------- | ------------- | ------------- | ------------------- | --------------- | -------------- |
| DIN-SQL 简化实现（修正后） | 30/30（100%） | 10/10         | 8/10                | 9/10            | 27/30（90%）   |
| Baseline                   | 30/30（100%） | 10/10         | 6/10                | 9/10            | 25/30（83.3%） |

本批样本中，DIN-SQL 简化实现比 baseline 多匹配 2 道，分别为样本 37、53，结果匹配率高约 6.7 个百分点。差异出现在 NON-NESTED 组；EASY、NESTED 两组的匹配数相同。

以上结果仅描述本批 30 道样本上的简化实现与 baseline 对比，不代表原版 DIN-SQL 或完整 Spider dev 集的表现。
