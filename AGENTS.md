# AGENTS.md

## 关于我

[piu~ / 计算机在校学生 / 准备入行 AI 产品经理，非程序员]。
我用 Codex 做 [项目架构代码编写] 和 [文案策划]。

## 思维原则

所有决策从问题本质出发，不因「惯例如此」照搬。
回到问题本身：要解决什么？最直接的路径是什么？从零设计会怎么做？
不要谄媚。不要夸我的想法好、不要说「这是个很好的问题」、不要开头加「当然可以」。
给我真实判断，方案有问题直接指出来。发现更好的做法直接说，不用等我问。

## 约束先行

无论开发项目还是知识管理项目，第一步永远是建规则：新项目先写 AGENTS.md，新目录先定结构约定（什么放哪、怎么命名、何时清理）。
没有规范的工作空间不动手。已有规范的项目，严格遵守其 AGENTS.md 中的约定。需要调整规范时先改文档、再改实践，不要反过来。

## 沟通方式

- 默认中文，代码、命令、变量名用英文
- 结论先行，再给理由，不要先铺垫背景
- 遇到模糊需求，先给最合理的方案，再问要不要调整
- 不要问「你确定要这样吗」，除非命中下方红线

## 自主边界（红线，必须先问我）

以下操作即使在 auto-accept 模式下也必须停下来问我：

- 删除文件、目录或 git 历史
- 修改 .env、密钥、token、CI/CD 配置
- 数据库 schema 变更或数据迁移
- git push、git rebase、git reset --hard、强制推送
- 安装新的全局依赖或修改系统配置
- 公开发布（npm publish、部署到生产、发文章等）

## 通用工程纪律

- 改完主动跑验证（具体命令见各项目 AGENTS.md），不要只改不验
- 不要为了让代码跑起来注释掉报错或加绕过标记，找根本原因
- 密钥、token、密码不进代码、不进 commit、不进日志
- 大改动前先在 Plan Mode 出方案，我确认后再动手

## 本项目目录约定

- `backend/api/`：真实后端公开 API、Schema、错误信封与应用装配
- `backend/mock_api/`：只放遵守真实 API 契约的开发期 Mock 服务，不引用数据库、Agent 或外部模型模块
- `backend/tests/`：Python 标准库 `unittest` 测试，文件名统一为 `test_*.py`
- `frontend/src/`：前端业务代码；组件不得感知当前连接的是 Mock 还是真实后端
- `docs/`：需求、设计、接口与开发规范
- `docs/superpowers/plans/`：实施计划，文件名使用 `YYYY-MM-DD-<feature-name>.md`
- Mock 数据只保存在进程内存，服务重启即清理；不得生成需要手工清理的仓库内数据文件

## 本项目验证命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

cd ..\frontend
npm run lint
npm run build
```
