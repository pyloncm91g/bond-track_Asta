# 債券質借風控儀表板 (Bond Collateral Risk Dashboard)

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg)](https://www.sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 專案簡介 (Overview)

**債券質借風控儀表板**是一套專為金融與債券投資質借業務打造的現代化風險控管系統。本系統採用 FastAPI 與 SQLite 輕量高效率架構，提供即時債券市值估算、質押維持率監控、追繳警戒通報及投組風險分析，協助風控人員與投資者精確掌握擔保品價值變動，預防違約與流動性風險。

---

## 核心功能 (Features)

- 📊 **質押維持率動態監控**：即時計算各質借合約之擔保品維持率，自動劃分安全、預警、追繳三大風險等級。
- 🔍 **債券行情與估值爬取**：內建異步網路爬蟲與行情解析引擎，支援多市場債券報價更新與公允價值試算。
- 📑 **ISIN 代碼批次管理**：支援國際證券識別碼 (ISIN) 批次匯入、檢核、自動比對債券基本資料與票面條件。
- 📈 **敏感度與壓力測試**：評估利率波動與價格下跌對質押成數之影響，輔助決策。
- 🐳 **完整容器化與高可用部署**：提供 Dockerfile 與 Docker Compose 配置，具備容器自動重啟 (`unless-stopped`)、健康檢查 (`healthcheck`) 與資料持久化功能。
- 🌐 **全繁體中文介面**：貼合在地作業流程與金融專業術語規範。

---

## 技術堆疊 (Tech Stack)

| 領域 | 技術項目 | 說明 |
| :--- | :--- | :--- |
| **後端框架** | [FastAPI](https://fastapi.tiangolo.com/) (0.104.1) | 高效能非同步 Web API 框架 |
| **ASGI 伺服器**| [Uvicorn](https://www.uvicorn.org/) (0.24.0) | 快速非同步 ASGI 伺服器實作 |
| **資料儲存 / ORM** | [SQLite](https://www.sqlite.org/) / [SQLAlchemy](https://www.sqlalchemy.org/) (2.0.23) | 輕量關聯式資料庫與現代 ORM |
| **資料模型 / 驗證**| [Pydantic](https://docs.pydantic.dev/) (2.5.2) | 嚴謹的資料型別驗證與序列化 |
| **爬蟲與 HTTP 客戶端**| [HTTPX](https://www.encode.io/httpx/) / [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) / [lxml](https://lxml.de/) | 高並發非同步 HTTP 請求與 HTML/XML 解析 |
| **容器化技術** | [Docker](https://www.docker.com/) / Docker Compose | 輕量化容器封裝與多環境編排 |

---

## 快速開始 - Docker 部署 (Quick Start with Docker)

### 1. 先決條件
- 已安裝 [Docker](https://docs.docker.com/get-docker/) 與 [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

### 2. 環境設定
複製範本設定檔並根據實際需求調整：
```bash
cp .env.example .env
```

### 3. 啟動服務
使用 Docker Compose 一鍵建置並於背景啟動容器：
```bash
docker compose up -d --build
```

服務啟動後，本機連接埠對應如下：
- **儀表板首頁 / 服務位址**：[http://localhost:48019](http://localhost:48019)
- **API 互動式文件 (Swagger UI)**：[http://localhost:48019/docs](http://localhost:48019/docs)
- **API 替代文件 (ReDoc)**：[http://localhost:48019/redoc](http://localhost:48019/redoc)
- **系統健康檢查**：[http://localhost:48019/api/health](http://localhost:48019/api/health)

### 4. 容器運維指令
- **檢視容器運行狀態**：
  ```bash
  docker compose ps
  ```
- **即時檢視日誌**：
  ```bash
  docker compose logs -f bonds-dashboard
  ```
- **停止並移除容器**：
  ```bash
  docker compose down
  ```

> [!NOTE]
> SQLite 資料庫檔案掛載於本機 `./data` 目錄，容器重啟或更新時資料庫內容完整保留。
> 重啟策略設定為 `restart: unless-stopped`，在 Docker 常駐守護行程啟動時可隨主機開機自動啟動。

---

## 本地開發指南 (Development Setup)

若需在本地直接除錯或開發：

### 1. 建立並啟動 Python 虛擬環境
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. 安裝相依套件
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 建立資料庫目錄
```bash
mkdir data
```

### 4. 啟動熱重載開發伺服器
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
存取本地開發環境：[http://localhost:8000](http://localhost:8000)

---

## API 規格摘要 (API Documentation Summary)

系統提供符合 OpenAPI 規範之 RESTful API，主要端點說明如下：

| 方法 | 路徑 | 功能說明 |
| :--- | :--- | :--- |
| `GET` | `/api/health` | 系統健康狀態檢查與探針 |
| `GET` | `/api/bonds` | 取得所有註冊之債券清單與當前市值 |
| `POST` | `/api/bonds` | 新增或註冊單筆債券資訊 (ISIN、票面利率、到期日等) |
| `POST` | `/api/bonds/import` | 批次匯入 ISIN 代碼清單 |
| `GET` | `/api/loans` | 查詢所有質借合約與質押部位 |
| `POST` | `/api/loans` | 建立質借合約與擔保品分配 |
| `GET` | `/api/risk/maintenance-ratios` | 取得全合約質借維持率及風險燈號清單 |
| `POST` | `/api/market/crawl` | 手動觸發即時債券行情爬取與重新估值 |

完整端點參數與請求模型定義可於啟動後瀏覽 `/docs` 查看。

---

## 專案目錄結構 (Project Structure)

```text
bonds/
├── app/                      # 應用程式主要原始碼目錄
│   ├── main.py               # FastAPI 應用入口與路由整合
│   ├── core/                 # 核心設定與組態 (Config, Security)
│   ├── models/               # SQLAlchemy 資料庫模型
│   ├── schemas/              # Pydantic 資料驗證模型
│   ├── routers/              # API 路由模組 (bonds, loans, risk 等)
│   ├── services/             # 商業邏輯 (爬蟲、維持率計算、估值)
│   └── db/                   # 資料庫連線與 Session 管理
├── data/                     # SQLite 資料庫儲存路徑 (掛載磁碟區)
│   └── bonds.db              # 預設資料庫實體檔案
├── .dockerignore             # Docker 建置忽略清單
├── .env.example              # 環境變數設定範本
├── .gitignore                # Git 版本控制忽略清單
├── docker-compose.yml        # Docker 服務編排設定檔
├── Dockerfile                # Docker 映像檔建置規格
├── requirements.txt          # Python 相依套件清單
└── README.md                 # 專案中文說明文件
```

---

## 授權條款 (License)

本專案採用 [MIT License](LICENSE) 授權開放。
