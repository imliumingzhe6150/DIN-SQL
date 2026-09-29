r

# DIN-SQL 学习与复现指南

## 目标

这不是把旧仓库勉强运行起来，而是先理解 DIN-SQL 的推理逻辑，再实现一个可测试、可替换模型的现代版本。

最终应能回答：

1. 为什么先做 schema linking，而不是直接生成 SQL？
2. EASY、NON-NESTED、NESTED 三类如何改变生成策略？
3. decomposition 给复杂查询带来了什么？
4. self-correction 能修复什么，不能修复什么？

## 系统主流程

```text
自然语言问题 + 数据库 schema
            |
            v
1. Schema Linking
   选择相关表、列、外键和问题中的常量
            |
            v
2. Classification & Decomposition
   EASY / NON-NESTED / NESTED
            |
            v
3. SQL Generation
   按类别选择不同 prompt
            |
            v
4. Self-Correction
   检查字段、JOIN、DISTINCT、GROUP BY 等
            |
            v
       最终 SQLite SQL
```

这是一条固定的 prompt pipeline，不是能够自主选择任意工具的通用 Agent。

## 官方源码阅读顺序

不要从第 1 行一直读到最后。按下面顺序阅读：

1. `DIN-SQL.py:602`：主循环，先看数据怎样流过四个模块。
2. `DIN-SQL.py:490`：schema-linking prompt 的组装。
3. `DIN-SQL.py:478`：分类与分解 prompt 的组装。
4. `DIN-SQL.py:452`、`:462`、`:471`：三类 SQL 生成 prompt。
5. `DIN-SQL.py:555`：self-correction prompt。
6. `DIN-SQL.py:9`、`:174`、`:246`、`:303`、`:346`：各模块的 few-shot 示例。
7. `DIN-SQL.py:522`：Spider `tables.json` 如何被转换成表、列和外键文本。

## 第一天任务（约 90 分钟）

### 任务 1：只读主循环

从 `DIN-SQL.py:602` 开始读到文件末尾，为每个阶段记录：

- 输入是什么？
- 输出是什么？
- 输出如何传给下一阶段？
- 哪一步可能失败？

### 任务 2：手工走一条 EASY 样例

问题：`How many singers do we have?`

预期中间结果：

```text
Schema links: [singer.*]
Class: EASY
Generated SQL: SELECT COUNT(*) FROM singer
Corrected SQL: SELECT COUNT(*) FROM singer
```

思考：这个问题为什么不需要 JOIN 或子查询？

### 任务 3：手工走一条 NON-NESTED 样例

问题：`Show the status of the city that has hosted the greatest number of competitions.`

先只回答：

- 需要哪些表？
- 使用哪条外键？
- 为什么需要 JOIN？
- 是否一定需要嵌套查询？

然后再查看 prompt 示例中的推理和 SQL。

### 任务 4：写下三个观察

至少记录：

1. 代码中的“decomposition”实际发生在哪里。
2. 分类错误会怎样传导到 SQL 生成。
3. self-correction 没有执行数据库查询，它只是再次调用 LLM 检查文本。

## 当前仓库的运行风险

- `API_KEY = #key` 是语法错误，官方文件不能直接执行。
- 使用 `openai==0.27.0` 和旧式 `openai.ChatCompletion.create`。
- 模型名和当前可用模型可能不同。
- 异常处理使用无限重试，真实错误可能被隐藏。
- README 只要求 `tables.json` 和 `dev.json`；如果要做执行准确率，还需要 Spider 的 SQLite 数据库文件和评测程序。
- 一次完整运行会对每个样本进行多次模型调用，不适合作为第一次测试。

因此后续复现应先支持单个样例、保存每个模块的输入输出、限制重试次数，再扩展到完整 dev set。

## 进入下一阶段的标准

完成第一天任务后，如果能不看代码画出四模块数据流，并解释三种分类的区别，就进入下一步：

1. 准备 Spider 数据；
2. 建立隔离环境；
3. 写一个不调用 LLM 的 prompt-inspection 脚本；
4. 再接入当前模型 API 跑 1 个样例。
