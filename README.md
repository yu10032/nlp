# 课程智能助教系统

以课程资料和知识图谱连接提问、答疑、出题与课堂讲义，支持原文核查、人工审核和版本追溯。技术栈为 Vue 3 + FastAPI + SQLite，本地匹配模型单独维护。

## 安装与启动

要求 Python 3.12+、Node.js 22.12+。以下命令在仓库根目录执行，本机为 `D:\code_ai\NLP\work`。

```powershell
# 首次安装
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt -e "./backend[dev]"
npm.cmd --prefix frontend ci

# 新库或升级现有数据库
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
# 可选：导入少量手工示例
.\.venv\Scripts\python.exe -m ta_backend.seed
```

日常使用双击仓库根目录的 `start.cmd`：它会在后台启动前后端，等待两边就绪后才打开工作台；重复启动会复用已就绪的服务。关闭浏览器后服务仍运行，双击 `stop.cmd` 停止由此入口启动的服务。启动失败时查看 `logs/` 下对应的输出和错误日志。

也可在终端执行（`-NoBrowser` 用于只启动服务，随后在内置浏览器打开地址）：

```powershell
.\scripts\start.ps1
# .\scripts\start.ps1 -NoBrowser
# .\scripts\start.ps1 -Stop
```

需要观察开发日志时，仍可在两个终端分别执行：

```powershell
.\scripts\start-backend.ps1
```

```powershell
.\scripts\start-frontend.ps1
```

工作台地址为 [http://127.0.0.1:5173](http://127.0.0.1:5173)，端口是 `5173`；[交互式接口文档](http://127.0.0.1:8000/docs) 由后端提供。手动启动的终端按 `Ctrl+C` 停止。重启电脑后需要再次启动服务，单独打开网页不会启动本地程序。更新代码后同步锁定依赖并执行迁移，当前数据库版本为 `0004`。

## 配置

首次配置参考 `.env.example` 创建 `.env`，已有文件直接编辑。在线生成使用：

```dotenv
TA_GENERATION_PROVIDER=external
TA_LLM_BASE_URL=服务基础地址及版本前缀
TA_LLM_MODEL=模型标识
TA_LLM_API_KEY=后端密钥
```

服务需兼容 Chat Completions 和 JSON 输出，基础地址不包含 `/chat/completions`。修改后重启后端；设为 `disabled` 可使用检索和手工编辑。生成请求会发送相关课程片段，结果需要教师审核。

本地句向量和 MLP 另用 `TA_MATCHER_RUN_DIR` 配置，准备方式见[训练说明](training/README.md)。留空时使用轻量词面方法；开发模型限定冻结课程图谱，自动策略当前为 TF-IDF。

## 使用与维护

- [文档目录](docs/README.md)：使用指南、架构、接口、标注规则和原始需求。
- [使用指南](docs/user-guide.md)：资料上传、图谱匹配、答疑、出题、分段讲义、审核与成品导出。
- 实验页可比较匹配模型，也可保存普通／图谱增强的证据对照、人工评价与历史。
- 提问页按批次整理问题，提供词面相似候选，支持确认、合并、移出和手动建组；原问题及模型预测保留。
- [界面规范](DESIGN.md) · [训练复现](training/README.md) · [部署说明](deploy/README.md)。

```powershell
.\scripts\check.ps1
```

检查后端业务、Python 格式和前端类型／构建。模型字段变动使用 Alembic 迁移，并同步前端类型和接口约定。

数据库与上传文件在 `data/runtime/`，模型在 `artifacts/`，密钥在后端 `.env`；这些本机数据不随 Git 分发。备份需要同时保存数据库、上传目录和配置。私人笔记、截图、导出放入被忽略的目录，提交前检查实际改动，忽略规则不清除既有历史。

当前用于本地协作，课程成员登录与权限尚未实现。后续重点为独立标签复核、真实教学质量评价和部署验收；开发指标不代表正式课程效果。
