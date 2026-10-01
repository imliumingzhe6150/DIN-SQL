import argparse
from pathlib import Path

from llm_client import call_llm
from inspect_prompt import (
    format_tables,
    format_foreign_keys,
    load_json,
    find_database_schema,
    execute_sql,
    compare_results,
    save_result,
)


def make_baseline_prompt(question, schema):
    return f"""Generate a SQLite query to answer the question.
Return only SQL, without explanations or Markdown fences.

# Database schema
{format_tables(schema)}

Foreign_keys = {format_foreign_keys(schema)}

# Question
{question}

# SQL
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行单题 baseline")
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    data = root.parent / "data"

    examples = load_json(data / "dev.json")
    schemas = load_json(data / "tables.json")

    if not 0 <= args.index < len(examples):
        parser.error(f"--index 必须在 0 到 {len(examples) - 1} 之间")

    example = examples[args.index]
    question = example["question"]
    db_id = example["db_id"]
    schema = find_database_schema(schemas, db_id)

    database = data / "database" / db_id / f"{db_id}.sqlite"
    gold_rows = execute_sql(database, example["query"])
    ordered = bool(example["sql"]["orderBy"])

    result = {
        "sample_id": args.index,
        "question": question,
        "database": db_id,
        "gold_sql": example["query"],
        "generated_sql": None,
        "execution_success": False,
        "result_match": False,
        "error": None,
    }

    stage = "generation"

    try:
        prompt = make_baseline_prompt(question, schema)
        print("正在调用模型，直接生成 SQL……")
        generated_sql = call_llm(prompt)
        result["generated_sql"] = generated_sql
        print(generated_sql)

        stage = "execution"
        rows = execute_sql(database, generated_sql)
        result["execution_success"] = True

        stage = "comparison"
        result["result_match"] = compare_results(rows, gold_rows, ordered)
        print("与 Gold 结果是否匹配：", result["result_match"])

    except Exception as error:
        result["error"] = {
            "stage": stage,
            "type": type(error).__name__,
            "message": str(error),
        }
        print(f"{stage} 阶段失败：{error}")

    output = root / "results" / "baseline" / f"sample_{args.index}.json"
    save_result(output, result)
    print("结果已保存到：", output)