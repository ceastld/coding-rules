# coding-rules

可跨项目复用的开发规则与 Agent skills。按项目需要选择安装，项目自己的技术边界、验收标准和交付权限继续生效。

## Skills

| Skill | 用途 |
| --- | --- |
| [product-iteration](skills/product-iteration/SKILL.md) | 从用户目标或真实反馈选择可交付切片，实现、验证、记录成果，并在已授权的持续范围内推进下一项 |

`product-iteration` 不绑定某个产品、技术栈、操作系统或构建工具，也不要求额外 MCP、外部 skill 或运行服务。它读取项目现有约束与计划，复用仍然有效的验证；阶段完成与长期目标完成分别处理。

## 按项目安装

安装器只复制选中的 skill 到目标项目的 `.agents/skills/<skill-name>/`，不会安装到用户级全局目录，不修改项目配置或源码。安装器需要 Python 3.9+；安装后的 skill 是文本文件，没有 Python 运行依赖。

先把本仓库克隆到任意工具目录，或下载 ZIP 解压：

```sh
git clone https://github.com/ceastld/coding-rules.git
```

然后在需要这个 skill 的**目标项目根目录**执行，将第一条参数替换为本仓库的实际路径：

```sh
python "/path/to/coding-rules/scripts/install.py" --project . --skill product-iteration
```

Windows 示例（按自己的实际目录修改）：

```powershell
python "D:/tools/coding-rules/scripts/install.py" --project "D:/projects/my-app" --skill product-iteration
```

也可以手动将 `skills/product-iteration/` 整个目录复制到目标项目的 `.agents/skills/`。参考文件和可选的 `agents/openai.yaml` 随包复制，引用全部是相对路径。

项目级 `.agents/skills/` 是 Codex 支持的技能位置，见 [OpenAI 官方 Skills 说明](https://learn.chatgpt.com/docs/customization/overview#skills)。其它支持 `SKILL.md` 的 Agent 按其项目级目录约定复制整个 skill 目录；宿主的发现机制和工具能力仍以其文档为准。

### 已安装内容与更新

重复安装相同内容会成功且不重写。已存在的 skill 与仓库版本不同时，安装器拒绝覆盖；先检查项目中的自定义改动，再备份或移走旧目录并安装新版。多个 skill 会先完成全部预检，再开始复制。

安装是本地副本，仓库更新不会自动改变项目。卸载时移除该项目中的 `.agents/skills/product-iteration/` 即可；如果它已纳入版本控制，用项目既有的变更流程处理。需要可复现版本时，先将技能仓库切到明确的 commit 或 tag，再安装。

## 使用

在支持显式 skill 调用的宿主中，可以这样请求：

```text
使用 $product-iteration，按当前项目开发计划持续迭代。
```

也可限定单次任务：

```text
使用 $product-iteration，实现这条用户反馈对应的最小完整功能，验证后交付本地结果。
```

授权边界由用户和项目决定。安装 skill 不会自动授权提交、推送、合并、安装应用或发布，也不会创建后台定时任务。真实 GUI 等验证暂不可执行时，明确保留未验范围，再推进不依赖它的工作。

## 方法与适用边界

通用闭环是：理解用户结果 → 选择小而完整的切片 → 实现 → 受影响验证与审查 → 记录结果 → 按授权继续。

它适合已有方向的产品持续迭代，能帮助减少重复验证、流程遗漏和无效协调。产品方向仍需来自用户需求与真实反馈；提交数、工具调用数和测试数不能证明用户收益。效率提升目前没有统一 A/B 实测保证，评估方法见 [价值与学习](skills/product-iteration/references/value-and-learning.md)。

## 维护与检查

通用流程放在 `SKILL.md`，按需细节放在 `references/`；项目特有的脚本、架构和权限留在项目自身。避免把一次事故变成所有项目的固定流程。

安装器检查使用标准库测试，在本仓库根目录运行：

```sh
python -B -m unittest discover -s tests -v
```

`skills/product-iteration/` 使用 [MIT 许可证](skills/product-iteration/LICENSE)。该许可证仅适用于此目录；仓库其它内容沿用各自的许可安排。
