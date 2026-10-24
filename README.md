# VaultQ

VaultQ 是一个默认只读、可追溯的本地知识助手。它为 Obsidian Markdown 笔记建立本地索引，在回答问题时同时展示笔记名、标题路径、行号、原文片段和 Obsidian 跳转链接。

它不是一个脱离资料自由回答的聊天机器人：找不到可靠依据时，会明确回答“库里没有足够信息”。

## 功能

- 扫描 `笔记/`、`wiki/`、`outputs/` 中的 Markdown 文件
- 解析标题层级、YAML 标签与行内标签
- SQLite FTS5 关键词检索
- Nomic Embedding 语义检索与混合排序
- Nemotron 本地模型生成带 `[1]`、`[2]` 引用的回答
- 引用有效性检查、证据不足拒答和本地模型不可用时的离线降级
- 复习题、学习路径、待补知识点与馆藏统计
- 古典图书馆 / 档案室风格的 Vue 3 + TypeScript 界面
- 默认只读，不提供修改、创建或删除原笔记的接口

项目背景、设计原则与边界请阅读 [ABOUT.md](ABOUT.md)。

## 技术栈

- 后端：Python、FastAPI、Pydantic
- 索引：SQLite、FTS5
- 本地模型：LM Studio OpenAI-compatible API
- 对话模型：`nvidia/nemotron-3-nano-4b`
- Embedding：`text-embedding-nomic-embed-text-v1.5`
- 前端：Vue 3、TypeScript、Vite

## 运行要求

- Windows 10/11、macOS 或 Linux
- Python 3.11 或更高版本
- Node.js 20 或更高版本
- LM Studio
- 建议至少准备约 8 GB 可用内存；实际需求与模型量化版本、上下文长度有关

## 1. 获取项目

```bash
git clone <你的仓库地址>
cd VaultQ
```

也可以在 GitHub 页面下载 ZIP 并解压。

## 2. 安装后端依赖

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

## 4. 在 LM Studio 下载并启动本地模型

1. 安装并打开 LM Studio。
2. 在 LM Studio 的模型搜索页面下载一个 Nemotron 3 Nano 4B GGUF 模型。默认模型标识为 `nvidia/nemotron-3-nano-4b`。
3. 再下载 Nomic Embed Text v1.5 Embedding 模型。默认标识为 `text-embedding-nomic-embed-text-v1.5`。
4. 打开 **Developer** 页面，分别加载对话模型和 Embedding 模型。
5. 启动 LM Studio Local Server，端口使用 `1234`，并启用 OpenAI-compatible API。
6. 在浏览器访问 `http://127.0.0.1:1234/v1/models`。能看到两个模型的标识，即表示准备完成。

模型文件只需要从 LM Studio 内下载，不需要手动复制到本项目。不同版本的 LM Studio 可能显示稍有差异的模型标识；如果与默认值不同，请按“自定义配置”一节设置实际标识。

## 5. 指定 Obsidian 知识库

建议把知识库放在项目目录外，这样不会被误提交到 GitHub。

Windows PowerShell：

```powershell
$env:VAULTQ_ROOT = "D:\Obsidian\MyVault"
$env:VAULTQ_VAULT_NAME = "MyVault"
```

macOS / Linux：

```bash
export VAULTQ_ROOT="/home/your-name/Obsidian/MyVault"
export VAULTQ_VAULT_NAME="MyVault"
```

VaultQ 默认读取知识库里的以下目录：

```text
笔记/
wiki/
outputs/
```

不存在的目录会被跳过。如果不设置 `VAULTQ_ROOT`，则使用项目目录中的安全示例笔记。

## 6. 启动 VaultQ

Windows PowerShell 可以直接运行：

```powershell
.\start-vaultq.ps1
```

脚本会启动后端与前端。浏览器打开：

```text
http://127.0.0.1:5173/
```

macOS / Linux，或希望分别查看日志时，使用两个终端。

终端一：

```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

终端二：

```bash
cd frontend
npm run dev
```

后端 API 文档：`http://127.0.0.1:8000/docs`

## 自定义 LM Studio 配置

Windows PowerShell 示例：

```powershell
$env:LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LM_STUDIO_CHAT_MODEL = "nvidia/nemotron-3-nano-4b"
$env:LM_STUDIO_EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v1.5"
$env:LM_STUDIO_TIMEOUT = "90"
.\start-vaultq.ps1
```

macOS / Linux 使用同名的 `export` 环境变量即可。

## 首次索引与日常使用

1. 首次启动时，后端会扫描 Markdown 并建立 `.vaultq/index.db`。
2. 新片段会通过 LM Studio 的 Embedding 模型生成向量。
3. 打开“目录检索”可以搜索原文并跳回 Obsidian。
4. 打开“档案问答”可以获得带编号引用的本地模型回答。
5. 笔记有变化后，点击左侧“重新编目”。

大型笔记库首次生成向量可能需要几分钟，后续只处理缺少向量的片段。

## 测试与构建

后端测试：

```bash
python -m pytest backend/tests -q
```

前端类型检查与生产构建：

```bash
cd frontend
npm run build
```

在后端与 LM Studio 都已启动时，可以执行端到端问答测试：

```bash
python backend/tests/manual_rag_smoke.py
```

## 隐私与安全

- VaultQ 仅监听本机 `127.0.0.1` 的后端端口。
- 原始 Markdown 只读；应用只写入独立的 `.vaultq/index.db`。
- 问答和向量生成请求发送到本机 LM Studio，不需要云端 API Key。
- `.gitignore` 默认排除本地索引、虚拟环境、构建产物、`.env` 和项目目录内的个人笔记。
- 上传 GitHub 前仍建议执行 `git status`，确认没有误加入个人文件。

## 常见问题

### 页面显示“无法连接本地服务”

确认后端正在运行，并访问 `http://127.0.0.1:8000/api/health`。如果无法打开，请重新启动后端。

### 显示 LM Studio 未连接

确认 LM Studio Local Server 已启动、端口为 `1234`，并检查 `http://127.0.0.1:1234/v1/models`。

### 模型已下载但仍显示未就绪

下载并不等于加载。请在 LM Studio Developer 页面加载模型并启动服务器，同时确认模型标识与环境变量完全一致。

### 为什么只有一篇笔记就绪

开源包只包含一篇安全示例笔记。设置 `VAULTQ_ROOT` 指向自己的 Obsidian 库并重新编目后，馆藏数量会更新。

## 开源许可

本项目使用 [MIT License](LICENSE)。

