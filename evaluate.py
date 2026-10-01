import sqlite3
from pathlib import Path

from inspect_prompt import load_json, execute_sql, compare_results


ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"

GROUPS = {
    "EASY": [0, 2, 4, 6, 8, 10, 14, 18, 20, 39],
    "NON-NESTED": [22, 24, 33, 35, 37, 51, 53, 57, 75, 81],
    "NESTED": [12, 28, 30, 31, 41, 43, 59, 61, 65, 85],
}

STAGES = ["generated_sql", "corrected_sql"]


if __name__ == "__main__":
    examples = load_json(DATA / "dev.json")
    total = {stage: [0, 0] for stage in STAGES}

    for label, indices in GROUPS.items():
        counts = {stage: [0, 0] for stage in STAGES}
        classification_correct = 0

        for index in indices:
            result_path = ROOT / "results" / f"sample_{index}.json"
            if not result_path.exists():
                print(f"样本 {index}：缺少结果，请查看日志")
                continue

            result = load_json(result_path)
            example = examples[index]
            db_id = example["db_id"]
            database = DATA / "database" / db_id / f"{db_id}.sqlite"

            gold_rows = execute_sql(database, example["query"])
            ordered = bool(example["sql"]["orderBy"])
            classification_correct += result["predicted_class"] == label

            for stage in STAGES:
                try:
                    rows = execute_sql(database, result[stage])
                except sqlite3.Error as error:
                    print(f"样本 {index}，{stage}：执行失败，{error}")
                    continue

                counts[stage][0] += 1
                if compare_results(rows, gold_rows, ordered):
                    counts[stage][1] += 1
                else:
                    print(f"样本 {index}，{stage}：与 Gold 不匹配")

        print(f"\n{label}，计划样本数：{len(indices)}")
        print(f"预测类别与预设分组一致：{classification_correct}/{len(indices)}")

        for stage in STAGES:
            executed, matched = counts[stage]
            total[stage][0] += executed
            total[stage][1] += matched
            print(f"{stage}：执行成功 {executed}/10，结果匹配 {matched}/10")
        print()

    print("总计，计划样本数：30")
    for stage in STAGES:
        executed, matched = total[stage]
        print(
            f"{stage}："
            f"执行成功 {executed}/30 ({executed / 30:.1%})，"
            f"结果匹配 {matched}/30 ({matched / 30:.1%})"
        )