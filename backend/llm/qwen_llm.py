"""模型层 · 云端模型：DashScope 通义千问（OpenAI 兼容端点）。

改造点（对应 需求分析.md F5「在线大模型 token 统计」）：

**必须开启 `stream_usage=True`**。不开的话，流式响应的 chunk 上
`usage_metadata` 恒为 None，F5 的 `u` 事件永远不会下发 —— 实测就是这样：
开启前跑一轮问答，`c` 事件 13 次、`s` 事件 1 次、`u` 事件 0 次。
这是 F5 唯一的开关，漏了就整项功能静默失效（不报错，只是永远没有用量数据）。

兜底方案（`get_openai_callback`）本项目没走：它在流式场景下需要额外包裹调用链，
而 stream_usage 已被 DashScope 兼容端点支持，够用且改动最小。
"""

from langchain_openai import ChatOpenAI

# .env 由 utils.paths 统一加载（全项目唯一加载点，override=True 的必要性见该模块）。
from utils.paths import require_env

# 云端调用超时与重试。对应风险清单 R2（云端 API 额度耗尽或网络不通）：
# 不设超时的话，网络异常时请求会长时间挂住，前端只能干等，体验上等同于白屏。
REQUEST_TIMEOUT = 60
MAX_RETRIES = 2


class MyModel:  # 4 用法
    _model = None

    @staticmethod  # 1 个用法
    def get_model():
        if MyModel._model is None:
            MyModel._model = ChatOpenAI(
                model=require_env("MODEL_NAME"),
                # 流式输出：接口层靠它逐块下发 NDJSON 的 c 事件
                streaming=True,
                # 让流式响应带上用量统计（F5）。见模块 docstring —— 这个开关不能省。
                stream_usage=True,
                timeout=REQUEST_TIMEOUT,
                max_retries=MAX_RETRIES,
            )
        return MyModel._model


# 原来的 m.invoke 写在模块顶层，导致「只要 import 这个文件就会真的发一次 API 请求」，
# 既浪费额度又让模块无法被安全导入。放进 __main__ 里，直接运行本文件时行为不变。
if __name__ == "__main__":
    m = MyModel.get_model()
    rs = m.invoke(input="hi")
    print(rs.content)
    print("用量：", getattr(rs, "usage_metadata", None))
