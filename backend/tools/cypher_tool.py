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
from backend.utils.paths import require_env


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


@tool("cypher_tool", args_schema=CypherParams)  # 1个用法
def cypher_tool(query: str) -> dict:
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
            return {"code": 400, "msg": "cypher 语句为空"}
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
        return {"code": 200, "data": rs, "count": len(rs)}
    except Exception as e:
        # 不要吞掉异常信息：否则连接失败、密码错误、语法错误全都长成同一个 500，
        # 排查时完全没有线索。这里保留类型和原文。
        return {"code": 500, "msg": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    rs = cypher_tool.invoke({"query": "MATCH (n) RETURN n "})
    print(rs)
