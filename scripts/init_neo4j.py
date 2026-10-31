"""
把 PostgreSQL 中的医学数据导入 Neo4j 知识图谱
关系：
  (Symptom)-[:HAS_SYMPTOM]-(Disease)-[:BELONGS_TO]->(Department)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import asyncio
from neo4j import AsyncGraphDatabase
from sqlalchemy import text

from src.core.config import get_settings
from src.infra.database import engine

settings = get_settings()


async def clear_graph(driver):
    """分批清空旧数据，避免一次删除太多导致超时"""
    print("清空旧图谱数据...")
    async with driver.session() as session:
        while True:
            result = await session.run(
                "MATCH (n) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS c"
            )
            record = await result.single()
            deleted = record["c"]
            print(f"  删除了 {deleted} 个节点")
            if deleted == 0:
                break
    print("清空完成")


async def create_constraints(driver):
    """创建唯一性约束（自动建索引，保证 MERGE 幂等）"""
    print("创建约束...")
    constraints = [
        "CREATE CONSTRAINT disease_name IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT symptom_name IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT department_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE",
    ]
    async with driver.session() as session:
        for cypher in constraints:
            await session.run(cypher)
    print("约束创建完成")


async def import_data(driver):
    print("从 PostgreSQL 读取数据...")

    async with engine.connect() as conn:
        # 1. 科室
        result = await conn.execute(text("SELECT id, name FROM departments"))
        departments = result.fetchall()

        # 2. 疾病
        result = await conn.execute(text("""
            SELECT d.id, d.name, d.department_id, dep.name AS dept_name
            FROM diseases d
            LEFT JOIN departments dep ON d.department_id = dep.id
        """))
        diseases = result.fetchall()

        # 3. 症状
        result = await conn.execute(text("SELECT id, name FROM symptoms"))
        symptoms = result.fetchall()

        # 4. 疾病-症状关联
        result = await conn.execute(text("""
            SELECT ds.disease_id, d.name AS disease_name,
                   ds.symptom_id, s.name AS symptom_name
            FROM disease_symptoms ds
            JOIN diseases d ON ds.disease_id = d.id
            JOIN symptoms s ON ds.symptom_id = s.id
        """))
        relations = result.fetchall()

    print(f"科室: {len(departments)}, 疾病: {len(diseases)}, 症状: {len(symptoms)}, 关联: {len(relations)}")

    async with driver.session() as session:
        # ----- 导入科室 -----
        print("导入科室节点...")
        for dept in departments:
            await session.run(
                "MERGE (d:Department {name: $name}) SET d.pg_id = $pg_id",
                name=dept.name, pg_id=dept.id
            )
        print(f"  科室完成: {len(departments)}")

        # ----- 导入疾病 + 关联科室 -----
        print("导入疾病节点...")
        for i, dis in enumerate(diseases, 1):
            await session.run(
                """
                MERGE (d:Disease {name: $name})
                SET d.pg_id = $pg_id
                WITH d
                OPTIONAL MATCH (dep:Department {name: $dept_name})
                FOREACH (_ IN CASE WHEN dep IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (d)-[:BELONGS_TO]->(dep)
                )
                """,
                name=dis.name,
                pg_id=dis.id,
                dept_name=dis.dept_name,
            )
            if i % 500 == 0:
                print(f"  已处理疾病 {i}/{len(diseases)}")
        print(f"  疾病完成: {len(diseases)}")

        # ----- 导入症状 -----
        print("导入症状节点...")
        for i, sym in enumerate(symptoms, 1):
            await session.run(
                "MERGE (s:Symptom {name: $name}) SET s.pg_id = $pg_id",
                name=sym.name, pg_id=sym.id
            )
            if i % 1000 == 0:
                print(f"  已处理症状 {i}/{len(symptoms)}")
        print(f"  症状完成: {len(symptoms)}")

        # ----- 导入疾病-症状关系 -----
        print("导入疾病-症状关系...")
        for i, rel in enumerate(relations, 1):
            await session.run(
                """
                MATCH (d:Disease {name: $disease_name})
                MATCH (s:Symptom {name: $symptom_name})
                MERGE (d)-[:HAS_SYMPTOM]->(s)
                """,
                disease_name=rel.disease_name,
                symptom_name=rel.symptom_name,
            )
            if i % 2000 == 0:
                print(f"  已处理关联 {i}/{len(relations)}")
        print(f"  关联完成: {len(relations)}")


async def main():
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    try:
        await driver.verify_connectivity()
        print("Neo4j 连接成功")

        await clear_graph(driver)
        await create_constraints(driver)
        await import_data(driver)

        print("\n图谱导入完成！")
        print("可在 Neo4j Browser 执行以下查询验证：")
        print('  MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt')
        print('  MATCH p=(:Symptom {name:"发热"})-[]-(:Disease)-[]->(:Department) RETURN p LIMIT 20')
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())