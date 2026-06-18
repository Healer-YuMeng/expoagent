| 服务           | 端口 | 用途         |
| ------------- | ----: | ---------- |
| frontend      | 8006 | 前端访问入口     |
| backend       | 9008 | 后端 API     |
| postgres      | 5436 | PostgreSQL |
| redis         | 6396 | Redis      |
| minio api     | 9002 | MinIO API  |
| minio console | 9004 | MinIO 控制台  |

# General_ageng / YCIS 智能招生助手

> 单仓库说明文档。原先分散在 `docs/`、`backend/`、`frontend/`、`scripts/` 以及旧 `cfapi/` 目录下的 Markdown 文档内容已统一整理到本文件。

## 1. 项目概览

这是一个围绕“智能招生对话 + 线索管理 + 第三方渠道接入”搭建的前后端一体项目，核心目标是让家长可以通过 AI 对话完成初步咨询和信息采集，同时让招生老师在工作台里查看线索、跟进记录、预约状态和渠道信息。

项目主要由 4 部分组成：

1. `frontend/`
   Vue 3 + Vite 的前端，包含首页、家长对话页、老师工作台、登录与系统设置。
2. `backend/`
   FastAPI 后端，负责认证、会话、消息流、线索、知识库检索、老师端接口、企业微信回调等核心能力。
3. `backend/app/integrations/dustess/`
   后端集成层中的尘锋能力目录，既包含业务调用所需的 client / crypto，也包含联调用的 CLI 与 callback server。
4. `scripts/`
   本地开发、基础设施启动和管理员辅助脚本入口。

---

## 2. 当前目录结构

```text
General_ageng/
├── README.md
├── docker-compose.yml
├── .env
├── .env.example
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── integrations/
│   │   │   └── dustess/
│   │   │       ├── client.py
│   │   │       ├── config.py
│   │   │       ├── crypto.py
│   │   │       ├── event_utils.py
│   │   │       ├── cli.py
│   │   │       ├── main.py
│   │   │       └── server.py
│   │   ├── static/
│   │   └── main.py
│   ├── scripts/
│   ├── tests/
│   └── environment.yml
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── utils/
│   │   ├── views/
│   │   └── i18n/
│   ├── package.json
│   ├── tsconfig*.json
│   └── vite.config.ts
├── scripts/
│   ├── dev/
│   │   ├── start-backend.sh
│   │   └── start-frontend.sh
│   ├── ops/
│   │   └── start-infra.sh
│   ├── admin/
│   │   └── create-teacher.sh
│   └── lib/
│       └── common.sh
├── bb.sh
├── ff.sh
├── create_image.sh
└── create_teacher.sh
```

兼容入口说明：

- `bb.sh` 只是 `scripts/dev/start-backend.sh` 的兼容包装
- `ff.sh` 只是 `scripts/dev/start-frontend.sh` 的兼容包装
- `create_image.sh` 只是 `scripts/ops/start-infra.sh` 的兼容包装
- `create_teacher.sh` 只是 `scripts/admin/create-teacher.sh` 的兼容包装

---

## 3. 核心业务链路

### 3.1 家长端对话

入口路径：

- 首页：`/`
- 语言选择后进入家长对话启动页
- 实际会话页：`/parent/conversations/:id`

主要流程：

1. 前端创建匿名会话或恢复已有匿名身份
2. 家长发送消息
3. 后端写入消息
4. 后端检索知识库上下文
5. 后端流式调用 LLM 生成回复
6. 后端抽取结构化信息
7. 后端更新 `conversation_profiles`
8. 满足条件时创建或更新 `leads`
9. 满足预约条件时附加二维码或预约提示

相关文件：

- 前端状态：`frontend/src/stores/conversation.ts`
- 家长页面：`frontend/src/views/parent/StartChatView.vue`
- 家长聊天页：`frontend/src/views/parent/ChatView.vue`
- 家长路由：`frontend/src/router/index.ts`
- 后端家长路由：`backend/app/routers/parent.py`
- LLM 服务：`backend/app/services/langchain_service.py`

### 3.1.1 渠道二维码归因与统计

这项功能的核心不是“生成一张二维码图片”，而是为不同投放平台生成带 `source` 参数的独立入口，并把来源信息贯穿到访问、会话、预约和线索。

业务上可以把它理解为：

- 每个平台对应一个专属入口，例如 `/?source=xhs`
- 家长扫码进入后，系统记录“这个家长最初从哪个渠道进来”
- 后续如果形成预约，系统把预约数归到该渠道
- 老师工作台按渠道展示访问量和预约量

业务流程图：

```mermaid
flowchart LR
    A[老师配置落地页地址] --> B[系统为各渠道生成带 source 的链接/二维码]
    B --> C[家长扫码进入落地页]
    C --> D[前端识别 URL 中的 source]
    D --> E[将来源写入 sessionStorage]
    E --> F[首次进入时上报 visit]
    E --> G[家长进入咨询流程并创建会话]
    G --> H[后端在 conversation.source_channel 中保存渠道]
    H --> I[对话中持续收集信息并创建或更新 lead]
    I --> J{是否形成预约}
    J -- 否 --> K[保留来源信息用于后续跟进]
    J -- 是 --> L[记录 appointment]
    L --> M[将 lead.source 归因到对应渠道]
    F --> N[老师工作台展示各渠道 visits]
    L --> O[老师工作台展示各渠道 appointments]
```

统计口径说明：

- `渠道`
  通过 URL 查询参数 `source` 识别，当前支持：
  `xhs` 小红书、`dy` 抖音、`blbl` 哔哩哔哩、`wb` 微博、`gzh` 微信公众号、`wxsp` 微信视频号。
- `visit`
  家长访问带有效 `source` 参数的落地页时记 1 次访问。
  当前按“浏览器会话 + 渠道”去重，同一浏览器会话内重复进入同一渠道链接不会重复计数。
- `conversation.source_channel`
  家长开始新会话时，将已识别的渠道写入会话，作为后续预约和线索归因依据。
- `appointment`
  当该会话在对话过程中形成预约信息后记 1 次预约。
  当前按“会话”去重，每个会话最多只会对同一渠道记录 1 次预约。
- `lead.source`
  新建线索时优先写入渠道来源；如果没有渠道来源，则写入 `chatbot`。
  如果已有线索后续补齐了渠道来源，线索来源会更新为该渠道。
- `source_stats`
  老师工作台按 `daily`、`monthly`、`yearly` 返回各渠道的 `visits` 和 `appointments` 汇总。

当前可以回答的业务问题：

- 今天/本月/今年各平台分别带来了多少访问
- 今天/本月/今年各平台分别带来了多少预约
- 哪些平台的预约转化更高

当前边界与限制：

- 这套统计目前覆盖的是“访问 -> 预约”漏斗，不等于最终报名、缴费或成交归因。
- 当前 `visit` 不是严格 UV，而是前端基于 `sessionStorage` 的轻量去重：
  同一用户更换浏览器、清空缓存、切换设备后，可能再次计数。
- 二维码图片目前由前端临时生成，后续可以替换为后端统一生成和托管的正式渠道码。
- 统计周期的日期键当前由后端 `UTC` 时间生成；如果业务口径要求按北京时间统计，需要单独调整。

### 3.2 老师工作台

主要能力：

- 账号登录
- 工作台数据总览
- 线索列表
- 线索详情
- 重点提醒 / 人工回访
- 欢迎语与系统提示词配置
- 用户管理

相关文件：

- 页面：`frontend/src/views/teacher/*`
- 路由：`backend/app/routers/teacher.py`
- 线索：`backend/app/routers/leads.py`
- 用户：`backend/app/routers/users.py`

### 3.3 第三方渠道与企业微信

企业微信回调用于补充或更新家长线索，不是主聊天入口。

相关文件：

- `backend/app/routers/wecom.py`
- `backend/app/services/wecom_service.py`

### 3.4 尘锋接口调试工具

`backend/app/integrations/dustess/` 下直接保留调试脚本，主要用于：

- 获取 `accessToken`
- 调用 `sendMsg`
- 调用 `directSendMsg`
- 解密回调内容
- 本地起一个 FastAPI callback 服务做对接验证

---

## 4. 技术栈

### 4.1 前端

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Vue I18n
- Axios
- Element Plus
- ECharts

### 4.2 后端

- Python 3.10+
- FastAPI
- PostgreSQL
- asyncpg
- Pydantic / pydantic-settings
- LangChain
- Chroma
- APScheduler
- JWT

### 4.3 本地依赖服务

当前 `docker-compose.yml` 启动：

- PostgreSQL
- Redis
- MinIO

当前端口：

- PostgreSQL: `5436`
- Redis: `6396`
- MinIO API: `9002`
- MinIO Console: `9004`

---

## 5. 环境准备

### 5.1 后端环境

推荐使用 Conda：

```bash
conda env create -n ycis -f backend/environment.yml
conda activate ycis
```

### 5.2 前端环境

```bash
cd frontend
npm install
cd ..
```

建议：

- Node.js 20.x LTS
- npm 跟随 Node 版本

### 5.3 Docker

需要本机安装：

- Docker Desktop
- 或可用的 `docker compose` / `docker-compose`

---

## 6. 环境变量

### 6.1 后端 `.env`

当前后端代码默认读取：

- 项目根目录 `.env`

首次使用：

```bash
cp .env.example .env
```

重要变量示例：

```bash
POSTGRES_HOST_PORT=5436
POSTGRES_URL=postgresql://postgres:password123@localhost:5436/General_ageng_admissions
POSTGRES_SSL=False
DB_NAME=General_ageng_admissions

LLM_PROVIDER=qwen
LANGCHAIN_CHAT_MODEL=qwen-plus
LANGCHAIN_EXTRACTION_MODEL=qwen-plus
LANGCHAIN_CHAT_TEMPERATURE=0.2
LANGCHAIN_CHAT_SYSTEM_PROMPT=
OPENAI_API_KEY=
QWEN_API_KEY=your-qwen-api-key
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
OLLAMA_BASE_URL=http://localhost:11434

EMBEDDING_PROVIDER=qwen
EMBEDDING_MODEL=text-embedding-v4
CHROMA_PERSIST_DIR=backend/data/chroma/vector_store
CHROMA_COLLECTION_NAME=General_ageng_kb

SECRET_KEY=replace-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

WECHAT_ADVISORS=[]
DEBUG=True
```

说明：

- 当前 demo 默认聊天模型示例为 `qwen-plus`
- 如果改用 Ollama，要同步配置 `OLLAMA_BASE_URL`
- 后端和 `cfapi` 现在统一从项目根目录 `.env` 读取配置

### 6.2 `cfapi` 的 `.env`

`cfapi` 当前默认读取：

- 项目根目录 `.env`

初始化方式：

```bash
cp .env.example .env
```

主要配置包括：

- `cf_agent_client_id`
- `cf_agent_client_secret`
- `cf_agent_callback_token`
- `cf_agent_encoding_aes_key`
- `cf_agent_receive_id`

---

## 7. 启动方式

项目本地运行通常需要 3 个终端。

### 7.1 启动基础依赖

推荐：

```bash
./scripts/ops/start-infra.sh
```

兼容旧入口：

```bash
./create_image.sh
```

### 7.2 启动后端

```bash
conda activate ycis
./scripts/dev/start-backend.sh
```

兼容旧入口：

```bash
./bb.sh
```

说明：

- 默认监听 `http://127.0.0.1:9008`
- 默认开启热重载
- 如果要关闭热重载：

```bash
BACKEND_RELOAD=0 ./scripts/dev/start-backend.sh
```

### 7.3 启动前端

```bash
./scripts/dev/start-frontend.sh
```

兼容旧入口：

```bash
./ff.sh
```

说明：

- 默认监听 `http://127.0.0.1:8006`
- 局域网访问：

```bash
FRONTEND_HOST=0.0.0.0 ./scripts/dev/start-frontend.sh
```

### 7.4 访问地址

- 首页：`http://localhost:8006`
- 登录页：`http://localhost:8006/auth/login`
- 后端 API 文档：`http://localhost:9008/docs`
- 健康检查：`http://localhost:9008/health`

---

## 8. 默认账号与辅助脚本

### 8.1 测试老师账号

当前项目中约定的测试账号：

- 手机号：`13800000002`
- 密码：`123456`

如果数据库中没有该账号，项目启动时会按当前初始化逻辑补齐。

### 8.2 创建老师账号

推荐：

```bash
./scripts/admin/create-teacher.sh 13800000003 测试老师 123456
```

兼容旧入口：

```bash
./create_teacher.sh 13800000003 测试老师 123456
```

---

## 9. 后端接口总览

这里只保留最常用和最关键的接口，便于开发与联调。

### 9.1 认证接口 `/api/v1/auth`

- `POST /login`
- `POST /logout`
- `GET /me`
- `POST /anonymous-session`
- `POST /register`
  当前仍存在，但从管理模型上看更适合由管理员统一建号

### 9.2 家长端接口 `/api/v1/parent`

- `GET /conversations`
- `POST /conversations`
- `GET /conversations/{conversation_id}`
- `GET /conversations/{conversation_id}/messages`
- `POST /conversations/{conversation_id}/messages`
- `DELETE /conversations/{conversation_id}`

家长发送消息后，后端会：

1. 检索 Chroma 知识库
2. 生成流式回复
3. 提取结构化信息
4. 自动更新线索
5. 命中关键词时写入 `manual_callbacks`

### 9.3 老师端接口 `/api/v1/teacher`

- 工作台摘要
- 欢迎语读取与更新
- 系统提示词读取与更新
- 线索相关老师视角接口

### 9.4 线索接口 `/api/v1/leads`

- 线索列表
- 线索详情
- 线索备注
- 回访状态
- 删除

### 9.5 文档与提示词接口

- 文档上传与知识库处理
- 提示词模板读取与更新

### 9.6 企业微信接口

- 事件回调接收
- 联系人匹配
- 自动回复
- 会话记录写入

---

## 10. 前端 API 映射

前端基础请求前缀统一为 `/api`。

### 10.1 认证

对应文件：

- `frontend/src/api/auth.ts`

核心函数：

- `login`
- `register`
- `getCurrentUser`
- `logout`
- `createAnonymousSession`

### 10.2 会话

对应文件：

- `frontend/src/api/conversation.ts`

核心函数：

- `getMyConversations`
- `createConversation`
- `getConversation`
- `closeConversation`
- `getConversationMessages`
- `sendMessage`

### 10.3 老师端

对应文件：

- `frontend/src/api/teacher.ts`
- `frontend/src/api/lead.ts`
- `frontend/src/api/users.ts`

---

## 11. API 测试示例

这里只保留最常用的几条，完整联调时建议直接看 `http://localhost:9008/docs`。

### 11.1 登录

```bash
curl -X POST "http://localhost:9008/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800000002","password":"123456"}'
```

### 11.2 创建匿名会话

```bash
curl -X POST "http://localhost:9008/api/v1/auth/anonymous-session" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 11.3 发送家长消息

```bash
curl -X POST "http://localhost:9008/api/v1/parent/conversations/<conversation_id>/messages" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"学校有哪些课程？"}'
```

---

## 12. 数据模型与数据库结构

### 12.1 核心集合

系统主要围绕以下集合展开：

1. `users`
2. `conversations`
3. `messages`
4. `conversation_profiles`
5. `leads`
6. `manual_callbacks`

### 12.2 关系概览

```text
users (parent / teacher / admin)
  ├── conversations
  │   └── messages
  ├── conversation_profiles
  └── leads
```

### 12.3 关键集合说明

#### `users`

用于存储：

- 家长
- 老师
- 管理员

关键字段：

- `phone`
- `password_hash`
- `role`
- `name`
- `email`
- `anonymous_id`
- `is_guest`
- `created_at`

#### `conversations`

用于存储会话元数据：

- `parent_id`
- `message_count`
- `last_message_at`
- `appointment`

#### `messages`

用于存储会话消息：

- `conversation_id`
- `sender_type`
- `content`
- `created_at`

#### `conversation_profiles`

用于缓存 AI 抽取出的结构化信息，例如：

- 家长姓名
- 电话
- 国籍
- 孩子年龄
- 意向校区
- 预约信息

#### `leads`

用于招生线索管理，典型字段：

- 家长信息
- 孩子信息
- 意向校区
- AI 摘要
- 预约状态
- 跟进状态
- 跟进人
- 企业微信信息

### 12.4 当前数据层痛点

整理自原重构建议与现状分析，当前主要问题有：

1. `users` 中家长和后台账号字段混用
2. 家长画像字段分散在 `users`、`conversation_profiles`、`leads`
3. 某些字段重复冗余
4. 渠道扩展能力还不够彻底配置化

后续更理想的方向：

- 将家长画像抽成更清晰的结构
- 缩减无效冗余字段
- 为多渠道接入预留统一模型
- 让报表与 BI 统计更自然

---

## 13. 知识库与 RAG

### 13.1 用途

知识库用于给招生助手补充事实性问答上下文，例如：

- 课程体系
- 开放日
- 校区特色
- 招生条件

### 13.2 数据来源

默认目录：

- `backend/data/knowledge_base`

### 13.3 向量化脚本

```bash
python backend/scripts/ingest_knowledge_base.py
```

自定义路径：

```bash
python backend/scripts/ingest_knowledge_base.py --root path/to/docs
```

### 13.4 本地检索验证

```bash
python backend/scripts/search_kb.py "开放日"
```

### 13.5 当前实现说明

- 使用 Chroma 持久化向量数据
- 支持父子分段检索
- 对话时实时注入到系统提示词

---

## 14. 脚本清单

### 14.1 开发脚本

- `scripts/dev/start-backend.sh`
- `scripts/dev/start-frontend.sh`

### 14.2 运维脚本

- `scripts/ops/start-infra.sh`

### 14.3 管理脚本

- `scripts/admin/create-teacher.sh`
- `backend/scripts/init_db.py`
- `backend/scripts/verify_config.py`
- `backend/scripts/generate_secret_key.py`
- `backend/scripts/ingest_knowledge_base.py`
- `backend/scripts/search_kb.py`

### 14.4 兼容入口

- `bb.sh`
- `ff.sh`
- `create_image.sh`
- `create_teacher.sh`

---

## 15. 尘锋调试工具使用说明

调试工具现在位于 `backend/app/integrations/dustess/`。

### 15.1 初始化

```bash
conda activate ycis
cp .env.example .env
cd backend
```

### 15.2 常用命令

```bash
python -m app.integrations.dustess.main show-config
python -m app.integrations.dustess.main token
python -m app.integrations.dustess.main send-msg --chat-id=xxx -t "测试消息"
python -m app.integrations.dustess.main direct-send --targets=id1,id2 -t "群发内容"
python -m app.integrations.dustess.main proxy /ai/v1/... -X POST --data '{"foo":"bar"}'
python -m app.integrations.dustess.main decrypt --signature=... --timestamp=... --nonce=... --echo=...
```

### 15.3 Callback 调试

```bash
uvicorn app.integrations.dustess.server:app --reload --host 0.0.0.0 --port 9008
```

回调路径：

- `/callback`

---

## 16. Docker 与本地基础设施

### 16.1 当前策略

- 前端本地跑
- 后端本地跑
- 数据与对象存储走 Docker

### 16.2 典型本地架构

```text
Browser
  -> Frontend :8006
  -> Backend  :9008
  -> PostgreSQL :5436
  -> Redis    :6396
  -> MinIO    :9002 / :9004
```

### 16.3 常见排查

1. 端口被占用
2. Docker 未启动
3. `.env` 缺失或模型配置不完整
4. Python 版本过低
5. Node 依赖未安装

---

## 17. 前端改造记录摘要

本项目最近一轮前端改造主要完成了：

1. 首页改成语言选择式入口
2. 首页接入动态背景，与登录页保持同类视觉效果
3. 家长聊天页改成固定高度的玻璃拟态布局
4. 顶部导航、消息区、输入区统一风格
5. 多语言入口补全
6. 老师头像、用户头像和消息气泡设计持续调整

当前视觉风格是：

- 浅色玻璃拟态
- 大面积动态涂抹背景
- 圆角消息卡片
- 居中的品牌首页

---

## 18. 已发现的主要问题与改进建议

整理自历史分析报告与当前代码观察，优先级较高的问题包括：

1. 默认管理员初始化逻辑需要谨慎检查，避免每次启动都覆盖已有账号
2. 注册接口曾存在返回未定义变量的风险
3. 部分招生时间或开放日信息容易因硬编码过期
4. 知识库的分块更新与向量同步要保持一致
5. 文档和实现容易发生漂移
6. 自动化测试覆盖仍然很弱

建议下一步治理顺序：

1. 先把 `parent.py + langchain_service.py + leads` 的主链路进一步模块化
2. 统一环境配置来源
3. 为老师端和家长端补最基础的回归测试
4. 给知识库导入和线索生成补联调脚本
5. 做更清晰的运行手册和部署手册

---

## 19. 配置与安全提示

1. 不要提交真实密钥到 Git
2. 生产环境必须替换 `SECRET_KEY`
3. 生产环境必须使用真实数据库密码和对象存储密码
4. 第三方回调密钥不要放在前端
5. 对外暴露服务前要确认 CORS、JWT、回调签名和日志脱敏配置

生成密钥：

```bash
python backend/scripts/generate_secret_key.py
```

验证配置：

```bash
python backend/scripts/verify_config.py
```

---

## 20. 故障排查

### 20.1 `./bb.sh` 启动时报 Python 类型注解错误

通常说明当前 Python 版本低于项目要求。请切到 Python 3.10+。

### 20.2 前端启动但接口报错

先检查：

1. 后端是否已启动
2. Vite 代理目标是否通向 `127.0.0.1:9008`
3. 浏览器访问 `http://localhost:9008/docs` 是否正常

### 20.3 PostgreSQL 连不上

检查：

1. `docker compose ps`
2. `POSTGRES_URL`
3. 映射端口 `5436`

### 20.4 聊天没有知识库效果

检查：

1. 是否执行过 `ingest_knowledge_base.py`
2. 向量库目录是否生成
3. Embedding 配置是否有效

---

## 21. 当前保留原则

这份 `README.md` 现在是仓库内唯一保留的 Markdown 说明文件。原来散落的文档已被合并后移除。

本次整理默认只清理以下“明确非核心内容”：

1. 多余的 Markdown 文档
2. 前端构建产物目录
3. 明显的临时测试脚本
4. 非项目必需的辅助安装脚本

不会默认删除：

1. 业务代码
2. 运行脚本
3. 环境模板
4. 真正的测试代码目录

---

## 22. 维护建议

后续如果继续维护这个仓库，建议遵守两条规则：

1. 新的项目级说明直接维护在本 `README.md`
2. 只有当某个目录必须拥有独立说明且确实经常单独发给外部团队时，再考虑恢复子目录文档
