from langchain_openai import ChatOpenAI

# .env 由 utils.paths 统一加载（全项目唯一加载点，override=True 的必要性见该模块）。
from backend.utils.paths import require_env


class MyModel:  # 4 用法
    _model = None

    @staticmethod  # 1 个用法
    def get_model():
        if MyModel._model is None:
            MyModel._model = ChatOpenAI(
                model=require_env("MODEL_NAME"),
                streaming=True
            )
        return MyModel._model


# 原来的 m.invoke 写在模块顶层，导致「只要 import 这个文件就会真的发一次 API 请求」，
# 既浪费额度又让模块无法被安全导入。放进 __main__ 里，直接运行本文件时行为不变。
if __name__ == "__main__":
    m = MyModel.get_model()
    rs = m.invoke(input="hi")
    print(rs.content)
