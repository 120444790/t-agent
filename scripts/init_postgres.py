"""
把 medical.json 导入 PostgreSQL
使用方法：uv run python scripts/init_postgres.py
"""

import json
import asyncio
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from src.infra.database import AsyncSessionLocal, engine
from src.modules.medical.model import (
    Department,
    Disease,
    Symptom,
    DiseaseSymptom,
)


DATA_PATH = Path(r"C:\Users\hyd\Downloads\medical.json")


async def load_jsonl(path: Path):
    """逐行读取 JSONL"""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


async def main():
    print("开始读取 medical.json ...")
    records = await load_jsonl(DATA_PATH)
    print(f"共读取 {len(records)} 条疾病记录")

    async with AsyncSessionLocal() as db:
        # ========== 1. 收集并插入科室 ==========
        print("处理科室...")
        dept_names = set()
        for rec in records:
            for d in rec.get("cure_department") or []:
                if d:
                    dept_names.add(d.strip())

        dept_map = {}  # name -> id
        for name in sorted(dept_names):
            # 先查是否已存在
            result = await db.execute(select(Department).where(Department.name == name))
            dept = result.scalar_one_or_none()
            if dept is None:
                dept = Department(name=name)
                db.add(dept)
                await db.flush()
            dept_map[name] = dept.id
        print(f"科室数量: {len(dept_map)}")

        # ========== 2. 收集并插入症状 ==========
        print("处理症状...")
        symptom_names = set()
        for rec in records:
            for s in rec.get("symptom") or []:
                if s:
                    symptom_names.add(s.strip())

        symptom_map = {}
        for name in sorted(symptom_names):
            result = await db.execute(select(Symptom).where(Symptom.name == name))
            sym = result.scalar_one_or_none()
            if sym is None:
                sym = Symptom(name=name)
                db.add(sym)
                await db.flush()
            symptom_map[name] = sym.id
        print(f"症状数量: {len(symptom_map)}")

        # ========== 3. 插入疾病 + 关联 ==========
        print("处理疾病...")
        success = 0
        for i, rec in enumerate(records, 1):
            name = (rec.get("name") or "").strip()
            if not name:
                continue

            # 检查是否已存在
            result = await db.execute(select(Disease).where(Disease.name == name))
            if result.scalar_one_or_none():
                continue

            # 取第一个科室作为 department_id
            dept_id = None
            depts = rec.get("cure_department") or []
            if depts:
                dept_id = dept_map.get(depts[0].strip())

            disease = Disease(
                name=name,
                description=rec.get("desc"),
                cause=rec.get("cause"),
                prevent=rec.get("prevent"),
                cure_lasttime=rec.get("cure_lasttime"),
                cured_prob=rec.get("cured_prob"),
                department_id=dept_id,
            )
            db.add(disease)
            await db.flush()

            # 插入疾病-症状关联
            for s in rec.get("symptom") or []:
                s = s.strip()
                if s and s in symptom_map:
                    db.add(DiseaseSymptom(
                        disease_id=disease.id,
                        symptom_id=symptom_map[s],
                    ))

            success += 1
            if i % 500 == 0:
                await db.commit()
                print(f"  已处理 {i}/{len(records)}")

        await db.commit()
        print(f"成功导入疾病: {success} 条")

    print("导入完成！")


if __name__ == "__main__":
    asyncio.run(main())