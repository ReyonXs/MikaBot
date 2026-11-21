# Mika

## How to start

1. generate project using `nb create` .
2. create your plugin using `nb plugin create` .
3. writing your plugins under `src/plugins` folder.
4. run your bot using `nb run --reload` .

## Documentation

See [Docs](https://nonebot.dev/)

## 聊天与海龟汤

运行前使用 uv sync 安装依赖，将模型配置加入项目根目录的 .env 或进程环境。两个插件由 src/plugins 自动发现。



| 场景 | 操作 |
| --- | --- |
| 聊天 | 私聊直接发文字，群内 @机器人，或发送 `/聊天 你的问题`。每人每个会话保留最近八轮。 |
| 清空上下文 | `/清空聊天` |
| 开局 | `/海龟汤 开始`，从内置题和网络题库中随机抽取。群内共用一局，私聊可单独玩。 |
| 推理 | `/海龟汤 问 这件事发生在室内吗？`，提交完整解释用 `/海龟汤 猜 我的推理是……`。 |
| 回顾 | `/海龟汤 提示` 逐条解锁提示。`/海龟汤 进度` 查看汤面、已用提示和最近六次推理。 |
| 结束 | 猜中会自动公布汤底。开局者也可以发送 `/海龟汤 揭晓`。 |

## 英文和缩写命令

| 操作 | 英文 | 缩写 |
| --- | --- | --- |
| 聊天、清空聊天 | `/chat hello`、`/reset` | `/c hello`、`/rc` |
| 开局 | `/soup start` | `/ts s` |
| 提问、猜汤底 | `/soup ask ...`、`/soup guess ...` | `/ts q ...`、`/ts g ...` |
| 提示、进度、揭晓 | `/soup hint`、`/soup status`、`/soup reveal` | `/ts h`、`/ts p`、`/ts r` |

主命令也可写作 `/hgt`、`/turtle`、`/汤`。子命令可以混用，例如 `/hgt 提示`。单发 `/ts` 查看帮助。

## 自动采集与题库

机器人运行时，首次启动会在后台采集，之后默认每隔 24 小时运行一次。下次采集时间保存在 SQLite 中，错过的采集会在重启后执行。每轮使用中英文关键词搜索公开网页，并准备固定来源作为补充。可访问的搜索结果会随地区和时间变化。

每轮最多送审三个网页，每页至多收录两题。模型筛选有明确汤底、可用是非题推理的内容，改写为中文并生成两级提示。入库前检查字段、原文引句和相似度。收录结果保存在 `data/soup-library.sqlite3`，下次开局即可抽到，揭晓时附原网页地址。模型审核会使用所配置服务的额度。

在 `.env` 中设置 `SOUP_AUTO_COLLECT=false` 可关闭后台采集。`SOUP_INTERVAL_HOURS=24` 可改成其他正整数小时。改动后重启生效。需要立即采集一次时运行：

```powershell
uv run python -m src.mika_games.soup_library
```

## 更换模型服务

在 `.env` 中修改以下三项并重启机器人。两个插件共用这组配置。接口采用 Chat Completions 格式，程序会在基础地址后追加 `/chat/completions`。需要 `/v1` 的服务应在基础地址中包含它。本地免鉴权服务可将密钥留空。

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=填写该服务的密钥
```

参考 [NoneBot 文档](https://nonebot.dev/docs/) 与 [Yogurt 启动指南](https://acidify.ntqqrev.org/yogurt/start)。
