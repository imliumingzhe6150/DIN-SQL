import json
from pathlib import Path

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

If the label is NESTED, also list the sub-questions.

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
Sub_questions: <list of sub-questions, or []>
"""

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    data_directory = project_root.parent / "data"

    dev_path = data_directory / "dev.json"
    tables_path = data_directory / "tables.json"

    dev_examples = load_json(dev_path)
    all_schemas = load_json(tables_path)

    # 先检查 Spider dev 集中的第一条问题
    example = dev_examples[0]

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

        # 暂时手写第一阶段的结果，用来调试第二阶段。
    # 当前问题是：How many singers do we have?
    schema_links = "[singer.*]"

    classification_prompt = make_classification_prompt(
        question=question,
        schema=schema,
        schema_links=schema_links,
    )

    print()
    print("=" * 70)
    print("即将交给 Classification 模型的 Prompt")
    print("=" * 70)
    print(classification_prompt)
