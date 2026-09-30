# CheckMate
### Collaborative Travel Packing App · 旅行行李清單協作應用

**English**
CheckMate helps travellers prepare packing lists and coordinate shared items with friends. Users can create trip checklists, mark essential items, assign responsibilities, and share lists with view-only or editing access. Weather information and an AI packing assistant provide suggestions that users review before adding to their lists.

**繁體中文**
CheckMate 協助旅客整理行李清單，並與朋友分工準備共同攜帶的物品。使用者可以建立旅行清單、標記必帶物品、分配物品負責人，並以唯讀或可編輯權限共享清單。應用程式結合天氣資訊與 AI 行李助手，提供物品建議，讓使用者確認後加入清單。

## Features · 主要功能

| English | 繁體中文 |
| --- | --- |
| Register, sign in and manage a personal profile | 註冊、登入及管理個人資料 |
| Create and edit packing lists, with essential-item labels | 建立及編輯行李清單，標記必帶物品 |
| Organise trip dates in a calendar | 透過日曆管理旅行日期 |
| Add friends, share lists and assign items | 新增朋友、共享清單及分配物品 |
| Choose view-only or editable sharing permissions | 設定唯讀或可編輯的共享權限 |
| View weather information and suggested packing items | 查看天氣資訊及攜帶物品建議 |
| Select AI suggestions to create a list or update an existing one | 選擇 AI 建議，建立新清單或更新現有清單 |
| Reuse templates and packing history | 重用清單範本及打包紀錄 |
| Switch themes, dark mode and English/Chinese interface text | 切換主題、深色模式及英文／中文介面文字 |

## Technology · 技術

| Layer / 層面 | Tools / 工具 | Purpose / 用途 |
| --- | --- | --- |
| Frontend / 前端 | React, Tailwind CSS, Framer Motion | Pages, state and interactions / 頁面、狀態及互動 |
| Backend / 後端 | Python, Flask, REST API | Requests and business logic / 請求處理及業務邏輯 |
| Storage / 資料儲存 | MySQL, SQLAlchemy | Users, lists and sharing relationships / 使用者、清單及共享關係 |
| Authentication / 身分驗證 | JWT, password hashing | Sign-in and protected API access / 登入及受保護的 API 存取 |
| Weather / 天氣 | Open-Meteo; optional fallback providers | Weather data and packing hints / 天氣資料及攜帶物品提示 |
| Assistant / 助手 | Configurable language-model APIs | Packing suggestions / 行李物品建議 |

React sends HTTP requests to Flask. The backend checks authentication and permissions, reads or updates the database, and returns JSON to the frontend.

React 透過 HTTP 請求連接 Flask。後端檢查登入身分及操作權限，讀取或更新資料庫，再將 JSON 結果傳回前端。

## Getting Started · 本機啟動

Use Node.js, Python 3.12 and a MySQL database. Run the following commands from the repository root. The examples use Windows PowerShell.

需要 Node.js、Python 3.12 及 MySQL 資料庫。以下範例使用 Windows PowerShell，請在倉庫根目錄執行。

### 1. Install backend dependencies · 安裝後端依賴

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

If `backend/.env` already exists, edit it instead of overwriting it. Set a long random `JWT_SECRET_KEY` and your database connection details. Create the MySQL database before starting the backend; the application creates its tables during startup.

若已有 `backend/.env`，請直接編輯，避免覆寫現有設定。設定足夠長的隨機 `JWT_SECRET_KEY` 及資料庫連線資訊。啟動後端前，請先建立 MySQL 資料庫；應用程式會在啟動時建立所需資料表。

For a lightweight local demo, you can instead set `DATABASE_URL=sqlite:///checkmate.db` in `backend/.env`. This uses a local SQLite file. Remove or comment out this setting when using MySQL.

如需簡化本機示範，可在 `backend/.env` 設定 `DATABASE_URL=sqlite:///checkmate.db`，改用本機 SQLite 檔案。使用 MySQL 時，請移除或註解此設定。

### 2. Start the backend · 啟動後端

```powershell
.venv/Scripts/python.exe backend/app.py
```

The API runs at `http://127.0.0.1:5000`.

API 位於 `http://127.0.0.1:5000`。

### 3. Start the frontend · 啟動前端

Open another terminal:

開啟另一個終端：

```powershell
npm install
npm start
```

Open `http://localhost:3000` and register an account. The development proxy forwards API requests to the backend. For a production frontend build, configure `REACT_APP_API_URL` with your backend URL.

開啟 `http://localhost:3000` 並註冊帳號。開發代理會將 API 請求轉送至後端。如需建立正式環境的前端版本，請將 `REACT_APP_API_URL` 設為後端網址。

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows Python paths; use `cp` to copy the environment template.

在 macOS／Linux 上，請使用 `python3 -m venv .venv`，並將 Windows 的 Python 路徑改為 `.venv/bin/python`；環境設定範本可用 `cp` 複製。

## External Services · 外部服務

**Weather / 天氣**
Open-Meteo requires internet access. Additional weather providers can be configured for fallback. The requested location comes from coordinates, a city or the configured default location.

Open-Meteo 需要網絡連線，亦可設定其他天氣服務作為備援。查詢位置來自經緯度、城市名稱或預設位置設定。

**AI packing assistant / AI 行李助手**
Configure an AI provider and its API key in `backend/.env`. Supported integrations include Moonshot, DeepSeek, SiliconFlow, DashScope and Gemini. Without a configured key, or when the model service fails, the backend can return rule-based suggestions. Users choose which items to import.

請在 `backend/.env` 設定 AI 服務及其 API 金鑰。現有整合包括 Moonshot、DeepSeek、SiliconFlow、DashScope 及 Gemini。未設定金鑰或模型服務失敗時，後端可提供規則式建議；使用者自行選擇要匯入的物品。

Keep real database passwords, JWT secrets and API keys out of Git.

請勿將真實資料庫密碼、JWT 密鑰或 API 金鑰提交至 Git。

## Project Structure · 專案結構

| Path / 路徑 | Description / 說明 |
| --- | --- |
| `src/App.jsx` | App state and page navigation / 應用程式狀態及頁面切換 |
| `src/pages/` | Checklist, calendar, profile and assistant pages / 清單、日曆、個人資料及助手頁面 |
| `src/components/` | Shared interface components / 共用介面元件 |
| `src/api.js` | Frontend API client and token handling / 前端 API 呼叫及 token 處理 |
| `backend/app.py` | Flask endpoints, database models and external integrations / Flask 接口、資料模型及外部服務整合 |
| `backend/seed_data.py` | Initial checklist data / 初始清單資料 |
| `backend/.env.example` | Environment configuration template / 環境設定範本 |

## Demo Flow · 示範流程

1. Register an account and create a packing list. / 註冊帳號並建立行李清單。
2. Add essential and optional items, then save the list. / 新增必帶及一般物品，再儲存清單。
3. Add a second user as a friend and demonstrate sharing permissions. / 新增另一位使用者為朋友，示範共享權限。
4. Ask the assistant for packing suggestions and import selected items. / 向助手查詢物品建議，並匯入選定物品。
5. Explore the calendar, weather information and reusable templates. / 查看日曆、天氣資訊及可重用的範本。

## Current Scope · 目前範圍

The assistant focuses on packing items. Sharing uses API-based saving and refreshing. Real-time simultaneous editing, conflict resolution and automated destination-specific trip planning are possible future improvements. Production deployment and live provider availability depend on your own configuration.

助手以行李物品建議為主。共享清單透過 API 儲存及重新載入。即時多人編輯、衝突處理及按目的地自動規劃旅行，可作為後續改進方向。正式環境部署及外部服務可用性，取決於實際設定。

## Development Updates · 開發更新

[Packing workflow improvements and regression tests / 打包流程改進及回歸測試](https://github.com/WeixinChenDEV/CheckMate/pull/1) are tracked separately in a pull request. Check its status to see which updates have been merged into the default branch.

打包流程改進及回歸測試由上述 Pull Request 另行追蹤。請查看其狀態，確認哪些更新已合併至預設分支。
