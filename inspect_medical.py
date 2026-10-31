import json

path = r"C:\Users\hyd\Downloads\medical.json"

with open(path, encoding="utf-8") as f:
    # 这是 JSONL 格式：每行一个 JSON 对象
    first_line = f.readline()
    record = json.loads(first_line)

print("字段列表:")
for key in record.keys():
    value = record[key]
    value_preview = str(value)[:80] + ("..." if len(str(value)) > 80 else "")
    print(f"  {key}: {value_preview}")