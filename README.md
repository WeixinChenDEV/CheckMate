# CheckMate — Collaborative Travel Packing App / 旅行行李清單協作應用

## English

CheckMate helps travellers organise what to pack and coordinate shared items with friends. Users can create dated trip checklists, mark essential items, assign items to collaborators, and share lists with view-only or editing access. Weather information and an AI packing assistant provide item suggestions that users can review before adding to their lists.

The application uses **React** for the frontend, **Flask REST APIs** for the backend, **MySQL** for persistent storage, and **JWT** for authentication. Templates, a trip calendar and reusable packing history support the preparation workflow. An optional SQLite configuration makes local demos easier to run.

## 繁體中文

CheckMate 協助旅客整理旅行所需物品，並與朋友分工準備共同攜帶的物品。使用者可以建立附有出發及返程日期的行李清單、標記必帶物品、分配物品負責人，並以唯讀或可編輯權限共享清單。應用程式結合天氣資訊及 AI 行李助手，提供物品建議，讓使用者確認後加入清單。

前端採用 **React**，後端使用 **Flask REST API**，以 **MySQL** 儲存資料，並透過 **JWT** 驗證登入身分。清單範本、旅行日曆及可重用的打包紀錄，方便使用者管理旅行準備流程。另提供可選的 SQLite 設定，簡化本機示範的啟動步驟。

## Features / 主要功能

| Feature | 功能 |
| --- | --- |
| Trip checklists with departure and optional return dates | 附出發及選填返程日期的行李清單 |
| View-only and editable sharing with friends | 與朋友共享清單，支援唯讀及編輯權限 |
| Essential-item labels and item assignment | 必帶物品標記及物品分工 |
| Weather information and packing suggestions | 天氣資訊及攜帶物品建議 |
| AI suggestions with user-selected checklist import | AI 物品建議，由使用者選擇後匯入清單 |
| Templates, calendar and reusable packing history | 清單範本、日曆及可重用的打包紀錄 |

**Scope / 功能範圍:** AI suggestions focus on packing items. Shared lists use API-based saving and refreshing; live simultaneous editing is a future improvement. / AI 建議以攜帶物品為主；共享清單透過 API 儲存及重新載入，即時多人編輯屬後續改進方向。

The development notes below cover local setup, verification and implementation details in Simplified Chinese. / 以下開發筆記以簡體中文說明本機啟動、驗證及實作細節。

## 快速运行（Windows PowerShell）

需要 Node.js 与 Python 3.12。以下命令在仓库根目录执行。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

修改 `backend/.env` 的 `JWT_SECRET_KEY`。示例文件启用 `DATABASE_URL=sqlite:///checkmate.db`，会创建本地演示数据库，无需安装 MySQL。若使用原项目的 MySQL 方案，注释该行并填写 MySQL 配置，先创建数据库，再启动服务。已有 `.env` 时请编辑它，不要覆盖自己的配置。

启动后端：

```powershell
.venv/Scripts/python.exe backend/app.py
```

在另一个终端启动前端：

```powershell
npm ci
npm start
```

前端通常位于 `http://localhost:3000`，开发代理转发到 `http://127.0.0.1:5000`。首次演示先注册账号。MySQL 为原项目存储方案；SQLite 是便于运行与测试的替代配置。

天气需要网络，主要调用 Open-Meteo；配置其他天气服务密钥后可使用已有的回退逻辑。AI 提供商可通过 `backend/.env` 配置；没有密钥或服务失败时使用本地规则式建议，不会伪装成模型输出。用户选择物品后才导入清单。

## 自动化验证

```powershell
npm test -- --watchAll=false --runInBand
.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
$env:CI='false'
npm run build
```

测试覆盖 AI 物品解析、行程日期输入和保存、认证、共享权限、天气参数与服务失败。后端测试使用独立内存数据库和模拟服务，不连接现有数据库或付费模型。前端目前存在继承的 lint 警告；构建会显示这些警告。GitHub Actions 会执行前端测试、构建和后端测试。

## 本次完善

- AI 清单解析兼容 Markdown 标题、编号、复选框和中英文标题；去重、保留必带优先级并排除提示/追问。
- 新建行程支持选填返程时间，保存时保留日期；最早可选时间使用本地时间。
- 不完整、非数字或越界天气坐标返回 400，不再悄悄查询默认城市。
- 天气服务不可用时温度显示未知，不再使用固定示例温度生成建议。
- 添加测试、CI 和本地演示配置。

查看 [项目与面试说明](docs/INTERVIEW_GUIDE.zh-CN.md)，了解项目定位、技术用途、实际限制与演示步骤。下文保留功能和架构说明，部署部分为可选方案，不表示已验证线上服务。

---

## 一、项目是做什么的

Checkmate（仓库 README 商品名也可称 OutboundApp）是一个 **出行 / 旅行场景下的打包清单 Web 应用**。用户可以创建 **带出发 / 结束日期的行程清单**，对物品进行 **勾选与编辑**；支持 **模板快速建单** 与 **日历** 管理行程。系统用户（注册账号）可以 **加好友**、把清单 **共享** 给他人（**只读** 或 **可共同编辑**），并把清单项 **指派** 给好友。首页集成 **当前天气** 与 **天气详情**，便于按天气调整携带物品。界面中部提供 **AI 助手**：可 **对话**、**根据对话生成新行程**，或 **向当前行程追加物品**。用户 **完成打包** 后，符合条件的行程会进入 **历史记录**，并支持 **从历史复用** 旧清单。界面支持 **多主题**、**深色模式**、**中文与英文** 切换。

技术选型上：前端为 **React** 单页应用，后端为 **Flask REST API**，数据持久化在 **MySQL**；用户会话使用 **JWT**，前后端分离，可部署在本地或云端。

---

## 二、我实现的主要功能（全量清单，便于核对）

**账号与身份**

- 用户 **注册**、**登录**；服务端返回 **JWT**，前端本地保存并在请求头携带 `Authorization: Bearer <token>`。
- **会话恢复**：有 token 时自动请求当前用户信息并拉取数据。
- **个人资料**：显示名、头像风格（与 Dicebear 等展示逻辑配合）。
- **修改密码**、**退出登录**、**注销账号**（删除用户及相关数据由后端处理）。

**清单与行程**

- **创建**行程：名称、图标、主题、物品列表、可选行程起止时间。
- **编辑**行程：增删改物品、**紧要**标记、勾选状态；拥有者可改名称、主题、协作者、归档状态、日期等。
- **删除**行程：仅 **拥有者** 可删，且 **预设类型**（非 `custom`）的清单不可删除。
- **快捷模板页**：从内置模板生成草稿，再进入创建流程保存为自有行程。
- **日历**：查看行程日期、修改起止时间、从指定日期 **新建** 行程草稿。
- **列表展示**：默认只展示 **未归档** 行程；归档行程由「完成打包」等逻辑触发。

**协作**

- **按用户名查找** 注册用户并发 **好友请求**；对方 **接受 / 拒绝**；展示 **入站 / 出站** 请求状态。
- **删除好友**；好友与注册用户通过 `linked_user_id` 等形式关联。
- **共享清单**：拥有者指定对方用户名，并设置 **仅查看**（`can_edit` 为假）或 **可编辑**（为真）。
- **取消共享**。
- **清单详情** 中可将物品 **指派** 给 `"me"` 或 `collaborators` 中登记的好友 id；服务端校验指派对象合法，否则返回 400。

**天气**

- 拉取 **当前天气** 与 **更细预报**（如按小时 / 按天）；支持经纬度、城市名或环境默认位置；数据来自 **Open-Meteo**（无需 API Key），失败时有降级展示。
- 前端可将 **天气相关建议** 合并进指定行程，并对「行程出发日是否与所选日一致」等做了限制，避免误加。

**AI 助手**

- 浮层 **对话**；可 **导入为新行程** 或 **向当前行程追加物品**（只读共享清单侧会限制写入）。
- 后端通过环境变量选择 **AI 提供商** 与 **API Key**；提供 **status** 接口仅报告是否配置、**不返回密钥**。

**历史与完成打包**

- **完成打包** 流程及成功页。
- **只读共享**（`access === shared`）不写历史、不归档。
- **拥有者** 在「当前时间已超过行程结束日或开始日（按前端 cutoff 逻辑）」时，会 **写入历史** 并将行程 **归档**；否则仍可能进入成功页但 **不记历史**。
- **历史列表**：单条删除、清空全部、**复用** 为新建行程（物品重新生成 id）。

**设置与个性化**

- **主题**：后端允许的主题键包括 `cinnamon`、`hazeBlue`、`sageGreen` 等。
- **深色模式**、**通知**、**声音**、**自动定位**、**界面语言**（`en` / `zh`）。
- 偏好与主题会 **同步到服务端**（`/api/preferences`）。

---

## 三、仓库怎么跑（本地）

**前端** 在仓库 **根目录**：`package.json` 中为 React 18、Tailwind、`react-scripts`（Create React App）。开发时配置了 **proxy** 指向 `http://127.0.0.1:5000`，本地一般 **不必** 设置 `REACT_APP_API_URL`，`npm install` 后 `npm start` 即可，API 会转发到本机后端。

**后端** 在 **`backend/`**：主逻辑集中在 **`app.py`**，依赖见 **`requirements.txt`**（Flask、Flask-CORS、Flask-SQLAlchemy、PyJWT、PyMySQL、python-dotenv 等）。**MySQL** 连接字符串与密钥放在 **`backend` 的环境变量**（如 `.env`）中，勿提交真实密码。

**认证约定**：除注册、登录、健康检查等少数接口外，多数接口需 **JWT**；请求头为 **`Authorization: Bearer <token>`**。

---

## 四、前端结构（方便审阅代码时定位）

入口为 **`src/index.js`** 与 **`src/App.jsx`**。项目 **未使用 React Router**，通过 **`currentView`**（如 `login`、`home`、`me`、`quick`、`calendar`、`settings`、`detail`、`create`、`success`）与 **`activeTab`** 切换主界面；**底部导航** 仅在 `home`、`quick`、`calendar`、`me` 时出现。

**HTTP 封装** 在 **`src/api.js`**（`API_BASE` 来自 `process.env.REACT_APP_API_URL`，生产构建时在平台注入）。

**页面** 在 **`src/pages/`**：`UserLogin`、`HomeDashboard`、`QuickScenariosPage`、`CalendarPage`、`MyProfileAndLibrary`、`SystemSettings`、`ChecklistDetail`、`CreateNewTrip`、`PackingSuccess`、`AIChatAssistant`。

**文案** 在 **`src/uiCopy.js`**、**`src/settingsCopy.js`**；**主题与常量** 在 **`src/constants/data.js`**。

---

## 五、后端数据模型（概念层）

**User**：用户名唯一、密码哈希、显示名、头像风格等。对外 JSON 里当前用户 **`id` 常为字符串 `"me"`**，与清单项里 **`assignedTo: "me"`** 一致；真实数据库整数 id 多在 **`db_id`**。

**Scenario**：复合主键（**拥有者 `user_id` + 字符串 `scenario_id`**）。字段包括 `name`、`icon`、`theme`（JSON）、`type`（默认 `custom`）、`items`（JSON 数组）、`collaborators`（JSON）、`archived`、`trip_start_at`、`trip_end_at` 等。

**Friend**：某用户的好友列表中的一行；**`linked_user_id` 非空** 表示已关联另一名 **注册用户**。

**FriendRequest**：好友请求（谁向谁、状态如 `pending` 等）。

**ScenarioShare**：拥有者将某 `scenario` 分享给另一用户；**`can_edit` 为 false 表示只读，为 true 表示可共同编辑 items**。

**HistoryRecord**：一条打包历史，可含 `scenario_id`、`name`、`date`、`status` 等。

---

## 六、HTTP API（路径列表）

`GET /api/health` — 健康检查。

`POST /api/auth/register` — 注册，返回 token 与公开用户信息；新用户会 seed 初始数据。

`POST /api/auth/login` — 登录，返回 token。

`GET`、`PUT`、`DELETE /api/me` — 当前用户资料；`DELETE` 为销号。

`PUT /api/me/password` — 修改密码。

`GET /api/users/lookup?username=` — 按用户名查询是否存在。

`GET`、`POST /api/friends/requests` — 列出好友请求（可带 `direction`）、创建请求。

`POST /api/friends/requests/<id>/accept` — 接受请求。

`POST /api/friends/requests/<id>/decline` — 拒绝请求。

`GET /api/friends` — 好友列表。

`DELETE /api/friends/<friend_id>` — 删除好友。

`POST /api/scenarios/<id>/share` — body 含 `username`、`can_edit`。

`DELETE /api/scenarios/<id>/share?username=` — 取消分享。

`GET /api/scenarios` — **自己的未归档行程** 与 **他人分享给我的行程**。

`POST /api/scenarios` — 创建；**必须同时提供 name 与非空 items**；校验行程开始不能在过去、结束不能早于开始。

`GET`、`PUT`、`DELETE /api/scenarios/<scenario_id>` — 读取、更新、删除；**仅拥有者可删**；**`type` 非 `custom` 的预设清单不可删**。

`GET`、`POST /api/history` — 历史列表、新增记录。

`DELETE /api/history/<record_id>` — 删除单条历史。

`DELETE /api/history` — 清空历史。

`GET`、`PUT /api/preferences` — 用户偏好（主题、深色、语言等）。

`POST /api/assistant/reply` — AI 对话，body 含 `message`，可选 `conversation`。

`GET /api/assistant/status` — 各 AI 后端是否配置（不返回密钥）。

`GET /api/weather` — 当前天气；query 可用 `lat`+`lon` 或 `city`；无参则用环境默认。

`GET /api/weather/detail` — 更细预报，参数规则同上。

---

## 七、清单访问模式与更新规则（核心逻辑）

列表中每条行程带有 **`access`**：**`owner`**（本人）、**`shared`**（他人分享、只读）、**`shared_edit`**（他人分享、可改内容）。被分享的行程还会带 **`owner_user_id`**、**`owner_username`** 等；本人拥有的行程可带 **`share_recipients`**（已分享给谁、每人 **`can_edit`**）。

**`PUT` 更新行程时**：**拥有者** 可更新 name、icon、theme、items、collaborators、archived、行程日期等。**非拥有者** 但 **`can_edit` 为真** 时，**仅能更新 `items`**；若尝试改名称、主题、日期等，返回 **403**。**只读共享** 不能改内容。

更新 **`items`** 时，每项的 **指派对象** 必须在允许集合内（含 **`"me"`** 与 **`collaborators`** 中登记的好友 id），否则 **400**。更新 **`collaborators`** 时，后端会 **同步** 与协作者相关的 **可编辑分享** 关系。

---

## 八、外部依赖（第三方服务）

**天气**：**Open-Meteo**，一般无需 API Key；异常时后端返回降级数据。

**AI**：依赖多个厂商的 **API Key** 与环境变量（如 `AI_PROVIDER` 及各家 Key）；**`/api/assistant/status`** 仅用于探测是否配置，**不泄露密钥**。

---

## 九、可选部署架构

可采用 **前后端分离**，例如 **Vercel（前端）+ Render（后端）+ Aiven（MySQL）**。关联 GitHub 的托管平台可以配置推送后部署，但当前仓库与本次本地检查不证明这些线上服务已部署成功。

**前端层（Vercel）**  
职责是托管 React **构建后的静态资源** 并使用 **全球 CDN** 加速。仓库关联 GitHub **主分支** 后，每次推送自动执行 **`npm run build`**。在 Vercel 中配置环境变量 **`REACT_APP_API_URL`**，值为 **Render 上 Flask 服务的公开根 URL**（构建时打入前端，使浏览器请求发往生产 API，而不再依赖开发用的 proxy）。

**后端层（Render）**  
职责是以 **Web Service** 运行 **Flask**，处理业务逻辑、调用 AI 厂商接口、校验 JWT。Linux 生产环境可额外安装 Gunicorn，使用 `gunicorn app:app`（工作目录为 `backend`）；当前 requirements.txt 未包含该生产服务器。现有 CORS 允许所有来源，正式部署前需要配置实际前端域名。**JWT 密钥、数据库连接串、各 AI API Key** 等应放在托管平台环境变量中。当前应用会自动创建表并尝试补充字段，连接已有数据库前应确认其适用范围。

**数据层（Aiven）**  
职责是提供 **高可用 MySQL**。应用连接串中配置 **SSL / CA 证书（如 ca.pem）** 以保证传输加密。因 Render 出口 IP 可能变化，Aiven 侧 **IP 白名单** 可按厂商说明配置（例如 **`0.0.0.0/0`** 放行，同时依赖强密码、TLS、最小权限账号控制风险）。

**整体请求链路**  
用户浏览器访问 **Vercel 上的站点** → 前端根据 **`REACT_APP_API_URL`** 向 **Render** 发起 REST 请求并携带 **JWT** → Render 校验 Token、执行业务逻辑、读写 **Aiven MySQL** → 返回 JSON → 前端更新 React 状态并渲染界面。

**与本地开发的差异**  
本地依赖 **`package.json` 的 proxy** 指向 `127.0.0.1:5000`；生产依赖 **`REACT_APP_API_URL`** 指向公网 API。两者互不冲突，分别对应开发机与线上环境。

---

## 十、审阅或二次开发时的总规则（一句话）

行程分为 **owner、shared、shared_edit**；**非拥有者** 更新时 **几乎只能改 items**；**创建行程必须带非空 items**；**删除行程** 仅 **拥有者** 且 **`type` 为 custom**；对外当前用户 **`id` 常为 `"me"`**；列表接口 **默认不返回已归档** 行程。

---

## 十一、仓库目录提示

**`src/`** — 前端源码。  
**`backend/`** — Flask 应用（主逻辑 **`app.py`**）。  
根目录 **`package.json`** — 前端脚本与开发代理。

---

以上即本课程项目 **功能范围、技术实现要点与部署方式** 的完整说明，可直接作为报告附录或答辩材料引用。
