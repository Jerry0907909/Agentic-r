"""工具层：把 Neo4j 医疗知识图谱查询封装成 LangGraph Agent 可调用的 Tool。

只读保护（F6，已完成）不动：查询走 `session.execute_read(...)`，这是
**Neo4j 服务端强制只读** —— 任何 CREATE / MERGE / DELETE / SET / REMOVE / DROP
都会被服务端直接拒绝。比用关键词黑名单过滤可靠得多：黑名单能被字符串与注释
绕过，也容易误伤正常查询。

本次改造（F4）只改返回结构：从「返回裸 dict」改为 `(content, artifact)`，
让「查了哪个关系、命中几行」这类来源信息不再在返回时被丢掉。
"""

import json
import re
import sys
from pathlib import Path

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.tools import tool
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

# .env 由 utils.paths 统一加载（全项目唯一加载点；
# override=True 的必要性、以及「拿 Aura 密码连本地」那个坑，见该模块注释）。
from utils.paths import require_env


class CypherParams(BaseModel):  # 1个用法
    query: str = Field(..., description="用于医疗知识图谱查询的cypher语句")


# 驱动只创建一次：GraphDatabase.driver 内部维护连接池，
# 每次调用都新建会让连接越积越多，最终耗尽服务端连接。
_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            require_env("NEO4J_BOLT_URL"),
            auth=(require_env("NEO4J_USER"), require_env("NEO4J_PASSWORD")),
        )
    return _driver


def _describe_query(q: str) -> tuple[str, str | None]:
    """从 Cypher 语句里尽力还原「查了什么」，生成人类可读的来源名。

    返回 (来源名, 目标标签)。解析失败不抛异常 —— 溯源信息是锦上添花，
    不能因为它解析不出来就让整个查询失败。

    目标格式对齐 接口文档.md §3.4.5 的示例：
        Disease:百日咳 → DISEASE_SYMPTOM → Symptom
    """
    labels = re.findall(r"\(\s*\w*\s*:\s*(\w+)", q)
    rels = re.findall(r"\[\s*\w*\s*:\s*(\w+)", q)
    name_literal = re.search(r"name\s*[:=]\s*[\"']([^\"']+)[\"']", q)

    target_label = labels[1] if len(labels) > 1 else (labels[0] if labels else None)

    if labels and rels:
        head = f"{labels[0]}:{name_literal.group(1)}" if name_literal else labels[0]
        tail = labels[1] if len(labels) > 1 else "?"
        return f"{head} → {rels[0]} → {tail}", target_label
    if rels:
        return f"图谱查询：{rels[0]}", target_label
    if labels:
        return f"图谱查询：{labels[0]}", target_label
    return "Neo4j 图谱查询", target_label


def _preview(rows: list[dict], limit: int = 5) -> str:
    """把查询结果的前几行压成一行预览，用于溯源卡片的 snippet。

    只取每个 dict 的第一个值 —— 图谱查询结果通常是 {"s.name": "阵发性痉挛性咳嗽"}，
    键名（s.name）对用户没有意义，值才有。
    """
    values: list[str] = []
    for row in rows[:limit]:
        for value in row.values():
            if value is not None and str(value).strip():
                values.append(str(value).strip())
                break
    return "、".join(values)


@tool("cypher_tool", args_schema=CypherParams, response_format="content_and_artifact")  # 1个用法
def cypher_tool(query: str) -> tuple[str, dict]:
    """
    执行Cypher查询语句，用于医疗知识图谱数据检索。
    本工具为**只读**：只能查询，不能新增/修改/删除数据。
    数据库模式说明：
        节点(Node labels):
            Category:疾病分类
            Check:检查项目
            Cureway:治疗方式
            Department:科室
            Disease:疾病
            Dishes:菜肴
            Drug:药物
            Food:食物
            Symptom:症状
        关系(Relationship types):
            DISEASE_ACOMPANY:疾病伴随疾病
            DISEASE_CATEGORY:疾病所属分类
            DISEASE_CHECK:疾病对应检查项目
            DISEASE_CUREWAY:疾病治疗方式
            DISEASE_DEPARTMENT:疾病就诊科室
            DISEASE_DISHES:疾病相关菜肴
            DISEASE_DO_EAT:疾病宜吃食物
            DISEASE_NOT_EAT:疾病忌吃食物
            DISEASE_DRUG:疾病可用药物
            DISEASE_SYMPTOM:疾病对应的症状
        节点属性(Property keys):
            只有 Disease 带属性：name、desc、cause、prevent、get_way、get_prob、
            cured_prob、cure_lasttime、cost_money、yibao_status
            其余 8 个标签（Symptom/Drug/Check/Food/Dishes/Cureway/Department/Category）
            都只有 name 一个属性；关系没有任何属性。
        图结构：所有关系都是单向的 (:Disease)-[:关系]->(目标节点)。
        典型写法：
            MATCH (d:Disease {name:"百日咳"})-[:DISEASE_SYMPTOM]->(s:Symptom)
            RETURN s.name
    """
    try:
        q = (query or "").strip().rstrip(";").strip()
        if not q:
            return _fail({"code": 400, "msg": "cypher 语句为空"})
        # 兜底限制返回条数。写语句不追加（追加会让语法报错，掩盖真正的
        # 「只读模式不允许写入」错误，反而误导排查）；已有 LIMIT 也不重复追加。
        is_write = re.search(
            r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH)\b", q, re.I
        )
        if not is_write and not re.search(r"\blimit\b", q, re.I):
            q += " LIMIT 10"

        driver = _get_driver()
        with driver.session() as session:
            # 用 execute_read 执行：这是服务端强制只读，任何写操作
            # （CREATE/MERGE/DELETE/SET/REMOVE/DROP…）都会被 Neo4j 直接拒绝。
            # 比用关键词黑名单过滤可靠得多——黑名单会被字符串/注释绕过，
            # 也可能误伤正常查询。
            rs = session.execute_read(lambda tx: [rec.data() for rec in tx.run(q)])

        payload = {"code": 200, "data": rs, "count": len(rs)}
        # content 给模型读：保持改造前的 JSON 结构不变，模型看到的信息量不减少
        content = json.dumps(payload, ensure_ascii=False)

        name, target_label = _describe_query(q)
        preview = _preview(rs)
        snippet = f"命中 {len(rs)} 条"
        if preview:
            snippet += f"：{preview}"
        # 图谱来源的 score 固定为 null —— 图谱命中是确定性的（有就是有、
        # 没有就是没有），不存在「相似度 0.83」这种概念（接口文档.md §3.4.5）。
        sources = [{
            "type": "graph",
            "name": name,
            "score": None,
            "snippet": snippet,
            "meta": {"cypher": q, "row_count": len(rs), "target_label": target_label},
        }]
        return content, {"sources": sources}

    except Exception as e:
        # 不要吞掉异常信息：否则连接失败、密码错误、语法错误全都长成同一个 500，
        # 排查时完全没有线索。这里保留类型和原文。
        return _fail({"code": 500, "msg": f"{type(e).__name__}: {e}"})


def _fail(payload: dict) -> tuple[str, dict]:
    """错误分支的返回。**不产生 sources** —— 查询失败不是「来源」，
    把它列进溯源卡片会误导用户以为这条答案是查到了东西才说出来的。"""
    return json.dumps(payload, ensure_ascii=False), {"sources": []}


if __name__ == "__main__":
    # 注意调用方式：`response_format="content_and_artifact"` 的工具，
    # 只有传 **ToolCall 结构**（即图内 ToolNode 的调用形式）才会装配出
    # 带 artifact 的 ToolMessage；传普通 {"query": ...} 只会拿到 content 字符串。
    msg = cypher_tool.invoke({
        "name": "cypher_tool",
        "id": "call_demo",
        "type": "tool_call",
        "args": {"query": "MATCH (d:Disease {name:'百日咳'})-[:DISEASE_SYMPTOM]->(s:Symptom) RETURN s.name"},
    })
    print("【给模型的 content】", msg.content[:300])
    print("【给前端的 sources】", json.dumps(msg.artifact["sources"], ensure_ascii=False, indent=2))
