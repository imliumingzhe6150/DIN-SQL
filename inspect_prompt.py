import argparse
import json
import re
import sqlite3
from pathlib import Path
from llm_client import call_llm

def load_json(file_path):
    """读取 JSON 文件并返回 Python 对象。"""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def find_database_schema(all_schemas, db_id):
    """根据 db_id，从 tables.json 中找到对应数据库结构。"""
    for schema in all_schemas:
        if schema["db_id"] == db_id:
            return schema;

    raise ValueError(f"找不到数据库：{db_id}")


def format_tables(schema):
    """把 Spider 的表和字段转换成 DIN-SQL 使用的可读形式。"""
    table_names = schema["table_names_original"]
    column_names = schema["column_names_original"]

    result = []

    for table_index, table_name in enumerate(table_names):
        # 原版 DIN-SQL 会给每张表添加一个 *
        fields = ["*"]

        for owner_index, column_name in column_names:
            if owner_index == table_index:
                fields.append(column_name)

        fields_text = ", ".join(fields)
        result.append(
            f"Table {table_name}, columns = [{fields_text}]"
        )

    return "\n".join(result)


def format_foreign_keys(schema):
    """把数字形式的外键下标转换成 table.column 形式。"""
    table_names = schema["table_names_original"]
    column_names = schema["column_names_original"]
    foreign_keys = schema["foreign_keys"]

    result = []

    for first_column_index, second_column_index in foreign_keys:
        first_table_index, first_column_name = (
            column_names[first_column_index]
        )
        second_table_index, second_column_name = (
            column_names[second_column_index]
        )

        first_table_name = table_names[first_table_index]
        second_table_name = table_names[second_table_index]

        result.append(
            f"{first_table_name}.{first_column_name} = "
            f"{second_table_name}.{second_column_name}"
        )

    return "[" + ", ".join(result) + "]"


def make_schema_linking_prompt(question, schema):
    """组装一个简化版 Schema Linking prompt。"""
    instruction = (
        "Find the schema links needed to generate a SQL query "
        "for the following question."
    )

    tables_text = format_tables(schema)
    foreign_keys_text = format_foreign_keys(schema)

    prompt = f"""# Instruction
{instruction}

# Database schema
{tables_text}

Foreign_keys = {foreign_keys_text}

# Question
{question}

# Answer
Schema_links:"""

    return prompt

def make_classification_prompt(question, schema, schema_links):
    """把问题、数据库结构和上一步的 schema_links 组装成分类 prompt。"""

    tables_text = format_tables(schema)
    foreign_keys_text = format_foreign_keys(schema)

    return f"""# Instruction
Classify the SQL query needed to answer the question.

Rules:
- If nested queries are needed, choose NESTED.
- If JOIN is needed but nested queries are not, choose NON-NESTED.
- If neither JOIN nor nested queries are needed, choose EASY.

If the label is NESTED, list the sub-questions needed to solve it.
Write Sub_questions as a JSON array of strings, using double quotes.
For other labels, write Sub_questions: [].

# Database schema
{tables_text}

Foreign_keys = {foreign_keys_text}

# Question
{question}

# Schema links
{schema_links}

# Output format
Reason: <brief explanation>
Label: <EASY, NON-NESTED, or NESTED>
Sub_questions: ["sub-question 1", "sub-question 2"] or []
"""

def parse_classification(answer):
    """从分类模块的回答中提取 Label。"""
    match = re.search(
        r'Label:\s*["\']?(NON-NESTED|NESTED|EASY)\b',
        answer,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(f"无法提取分类标签：\n{answer}")

    return match.group(1).upper()


def make_easy_sql_prompt(question, schema, schema_links):
    """为 EASY 类问题组装 SQL Generation prompt。"""
    return f"""# Instruction
Generate a SQLite query that answers the question.
This question needs neither JOIN nor nested queries.

Use only tables and columns from the schema.
Return only the SQL query, without explanations or Markdown fences.

# Database schema
{format_tables(schema)}

# Question
{question}

# Schema links
{schema_links}

# SQL
"""


def parse_sub_questions(answer):
    """提取分类模块输出的 JSON 子问题列表，格式错误时明确报错。"""
    match = re.search(r"Sub_questions:\s*", answer, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"分类回答缺少 Sub_questions：\n{answer}")

    try:
        sub_questions, _ = json.JSONDecoder().raw_decode(
            answer[match.end():].lstrip()
        )
    except json.JSONDecodeError as error:
        raise ValueError("Sub_questions 必须是使用双引号的 JSON 列表") from error

    if (
        not isinstance(sub_questions, list)
        or not sub_questions
        or not all(isinstance(item, str) and item.strip() for item in sub_questions)
    ):
        raise ValueError("NESTED 的 Sub_questions 必须包含至少一个非空字符串")

    return sub_questions


def make_nested_sql_prompt(question, schema, schema_links, sub_questions):
    """把分解出的子问题传给嵌套 SQL 生成模块。"""
    return f"""# Instruction
Generate a SQLite query that answers the original question.
This question requires nested queries or set operations.

Use the sub-questions to work out the inner queries, then combine them
into one SQL statement answering the original question.
Use only tables and columns from the schema.
Use foreign keys when JOIN is needed.
Check aggregation, NULL behavior, and the relationship between inner
and outer queries. Use set operations only when the question needs them.
Return only the final SQL, without explanations or Markdown fences.

# Database schema
{format_tables(schema)}

Foreign_keys = {format_foreign_keys(schema)}

# Original question
{question}

# Schema links
{schema_links}

# Sub-questions
{json.dumps(sub_questions, ensure_ascii=False, indent=2)}

# SQL
"""


def make_non_nested_sql_prompt(question, schema, schema_links):
    """为需要 JOIN、无需子查询的问题生成 SQL。"""
    return f"""# Instruction
Generate a SQLite query that answers the question.
This question needs JOIN but does not need nested queries.

Use only tables and columns from the schema.
Use foreign keys to identify the correct JOIN conditions.
Check whether aggregation and GROUP BY are needed.
Return only the SQL query, without explanations or Markdown fences.

# Database schema
{format_tables(schema)}

Foreign_keys = {format_foreign_keys(schema)}

# Question
{question}

# Schema links
{schema_links}

# SQL
"""


def execute_sql(database_path, sql):
    """以只读方式打开数据库，执行 SQL 并返回结果。"""
    database_path = Path(database_path).resolve()

    if not database_path.is_file():
        raise FileNotFoundError(f"数据库不存在：{database_path}")

    # mode=ro 表示只读，不会新建或修改数据库
    database_uri = database_path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)

    try:
        cursor = connection.execute(sql)
        return cursor.fetchall()
    finally:
        connection.close()


def make_self_correction_prompt(question, schema, generated_sql):
    """组装 SQL 检查与修正 prompt。"""
    return f"""# Instruction
Review the SQLite query against the question and database schema.

Check:
- Tables and columns
- JOIN conditions
- Filters
- Aggregation and GROUP BY
- DISTINCT, ORDER BY, and LIMIT
- Nested queries

Fix any errors. If the query is already correct, return it unchanged.
Return only the final SQL, without explanations or Markdown fences.

# Database schema
{format_tables(schema)}

Foreign_keys = {format_foreign_keys(schema)}

# Question
{question}

# SQL to review
{generated_sql}

# Final SQL
"""


def save_result(output_path, result):
    """保存一次运行的结果。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行一个 Spider 问题的四阶段流程")
    parser.add_argument("--index", type=int, default=0, help="dev.json 的样本下标")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    data_directory = project_root.parent / "data"

    dev_path = data_directory / "dev.json"
    tables_path = data_directory / "tables.json"

    dev_examples = load_json(dev_path)
    all_schemas = load_json(tables_path)

    if not 0 <= args.index < len(dev_examples):
        parser.error(f"--index 必须在 0 到 {len(dev_examples) - 1} 之间")
    example = dev_examples[args.index]

    question = example["question"]
    db_id = example["db_id"]
    gold_sql = example["query"]

    schema = find_database_schema(all_schemas, db_id)

    prompt = make_schema_linking_prompt(question, schema)

    print("=" * 70)
    print("即将交给 Schema Linking 模型的 Prompt")
    print("=" * 70)
    print(prompt)

    print()
    print("=" * 70)
    print("调试信息——不属于 Prompt")
    print("=" * 70)
    print(f"db_id: {db_id}")
    print(f"Gold SQL: {gold_sql}")

        # 第一次调用：获取真实的 Schema Linking 输出
    print("\n正在调用 DeepSeek：Schema Linking……")
    schema_links = call_llm(prompt)

    print("\nSchema Linking 模型回答：")
    print(schema_links)

    # 把第一阶段的回答传给第二阶段
    classification_prompt = make_classification_prompt(
        question=question,
        schema=schema,
        schema_links=schema_links,
    )

    print("\n即将交给 Classification 模型的 Prompt：")
    print(classification_prompt)

    # 第二次调用：获取分类结果
    print("\n正在调用 DeepSeek：Classification……")
    classification_result = call_llm(classification_prompt)

    print("\nClassification 模型回答：")
    print(classification_result)

        # 提取第二阶段返回的分类
    predicted_class = parse_classification(classification_result)
    print("\n解析出的分类：", predicted_class)

    # 第三阶段：根据分类选择生成策略
    if predicted_class == "EASY":
        sql_prompt = make_easy_sql_prompt(question, schema, schema_links)
    elif predicted_class == "NON-NESTED":
        sql_prompt = make_non_nested_sql_prompt(question, schema, schema_links)
    else:
        sub_questions = parse_sub_questions(classification_result)
        print("\n分解出的子问题：")
        print(json.dumps(sub_questions, ensure_ascii=False, indent=2))
        sql_prompt = make_nested_sql_prompt(
            question, schema, schema_links, sub_questions
        )

    print("\nSQL Generation Prompt：")
    print(sql_prompt)

    print("\n正在调用 DeepSeek：SQL Generation……")
    generated_sql = call_llm(sql_prompt)

    print("\n模型生成的 SQL：")
    print(generated_sql)

    print("\nGold SQL（仅用于核对）：")
    print(gold_sql)

    # 根据 db_id 找到对应 SQLite 数据库
    database_path = (
        data_directory / "database" / db_id / f"{db_id}.sqlite"
    )

    print("\n数据库路径：")
    print(database_path)

    try:
        predicted_result = execute_sql(database_path, generated_sql)
        gold_result = execute_sql(database_path, gold_sql)

        print("\n模型 SQL 的执行结果：")
        print(predicted_result)

        print("\nGold SQL 的执行结果：")
        print(gold_result)

        print("\n两者结果是否相同：")
        print(predicted_result == gold_result)

    except sqlite3.Error as error:
        print("\nSQL 执行失败：")
        print(error)

        # 第四阶段：检查并修正 SQL
    correction_prompt = make_self_correction_prompt(
        question=question,
        schema=schema,
        generated_sql=generated_sql,
    )

    print("\nSelf-Correction Prompt：")
    print(correction_prompt)

    print("\n正在调用 DeepSeek：Self-Correction……")
    corrected_sql = call_llm(correction_prompt)

    print("\n修正前的 SQL：")
    print(generated_sql)

    print("\n修正后的 SQL：")
    print(corrected_sql)

    try:
        corrected_result = execute_sql(database_path, corrected_sql)
        gold_result = execute_sql(database_path, gold_sql)

        print("\n修正后 SQL 的执行结果：")
        print(corrected_result)

        print("\n与 Gold SQL 的执行结果是否相同：")
        print(corrected_result == gold_result)

    except sqlite3.Error as error:
        print("\n修正后的 SQL 执行失败：")
        print(error)

    result = {
        "sample_id": args.index,
        "question": question,
        "database": db_id,
        "schema_links": schema_links,
        "classification_result": classification_result,
        "predicted_class": predicted_class,
        "generated_sql": generated_sql,
        "corrected_sql": corrected_sql,
        "gold_sql": gold_sql,
    }

    output_path = (
        project_root / "results" / f"sample_{args.index}.json"
    )

    save_result(output_path, result)
    print("\n结果已保存到：", output_path)
