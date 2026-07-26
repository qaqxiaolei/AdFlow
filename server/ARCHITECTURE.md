# AdFlow 后端架构（维护指南）

面向新人：改功能前先确认走哪条路径，再打开对应文件。

## 两条聊天路径

```
POST /api/chat
  → chat_service
  → LangGraph（planner → image_video_creator）
  → tool_service 注册的工具
  → 画布 + WebSocket 推送

POST /api/magic
  → magic_service
  → OpenAIAgents_service/jaaz_magic_agent（Jaaz 云端）
  → 与上面 LangGraph 无关
```

## 当前真正在用的 Agent

| Agent | 配置文件 | 职责 |
|-------|----------|------|
| planner | `services/langgraph_service/configs/planner_config.py` | 路由、交接 |
| image_video_creator | `services/langgraph_service/configs/image_video_creator_config.py` | 调图像/视频工具 |

## 主视频生成

- 工具名：`generate_video_by_agnes`（历史命名）
- 实际模型：火山方舟 **Seedance 2.0**（`volces_provider`）
- 场景约束增强：`tools/video_generation/video_prompt_utils.py`
- 时长上限：API 限制 **15 秒**；默认 15
- 分辨率默认 **1080p**（quantity=2 时可用 480p 提速）

## 改什么去哪改

| 需求 | 文件 |
|------|------|
| 奶茶/火锅画质与穿帮约束 | `tools/video_generation/video_prompt_utils.py` |
| 默认时长/分辨率 | `tools/generate_video_by_agnes.py` + agent 配置 |
| Agent 是否搜索、如何交接 | `planner_config.py` / `image_video_creator_config.py` |
| 工具是否对 AI 可见 | `services/tool_service.py` → `TOOL_MAPPING` |
| 流式推送 | `chat_service` + `StreamProcessor` + `websocket_router` |

## 工具注册

1. `TOOL_MAPPING` 声明工具
2. `tool_service.initialize()` 按已配置 API Key 过滤启用
3. Agent 从 `tool_service.get_tool(id)` 绑定

## 不要提交

- `server/user_data/`（含数据库、生成文件、jwt）
- `**/__pycache__/`
