# 漫剧制作 Skill

这是供 Codex 使用的漫剧制作 Skill。创作总控 Agent 审改语言模型产出的候选文字，统筹系列连续性、分镜、声音与成片验收。每集按前 3 秒冲突、15–20 秒爆点、至少 6 个有效话语落点、静默不超 8 秒、后 1/3 反转和“压→爆”推进。ArcReel 是可选的执行工具，并非所有项目的前提。

- [`SKILL.md`](SKILL.md)：Skill 入口、适用范围和关键决策。
- [`ARCREEL_PRODUCTION_PLAYBOOK.md`](ARCREEL_PRODUCTION_PLAYBOOK.md)：完整制作方法。
- [`references/series-production-engine.md`](references/series-production-engine.md)：强钩子叙事契约、系列连续性与验收规则。
- [`references/arcreel-execution.md`](references/arcreel-execution.md)：实际使用 ArcReel 时读取的适配规则。
- [`assets/templates/`](assets/templates/)：执行卡、任务包和分集叙事契约模板。
- [`scripts/validate_story_contract.py`](scripts/validate_story_contract.py)：分集叙事契约的结构校验。

把整个仓库文件夹放入 Codex 的 skills 目录，保留上述相对目录结构；仅复制手册文件不会安装 Skill。实际模型能力、费用和 ArcReel 接口以执行时的工具返回为准。

**许可说明：** 本仓库尚未附开放许可。公开可见不代表授予复制、修改或商用许可。
