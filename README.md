# AFM 智能操作助手

> 基于 RAG 检索增强生成 + 大语言模型的专业原子力显微镜知识库问答系统

## 产品定位

科研人员在使用 AFM（原子力显微镜）时面临两大痛点：
1. **操作手册冗长** — 仪器手册通常上百页，查找信息耗时
2. **培训内容遗忘** — 培训课程内容多，需要反复回看

本系统通过 **RAG 技术 + GLM-4 大模型**，让科研人员用自然语言提问即可获得精准操作指导，将"翻手册"变成"问助手"。

## 核心功能

| 功能 | 技术实现 | 价值 |
|------|---------|------|
| 智能问答 | RAG 检索 + GLM-4 生成 | 自然语言提问，直接获得操作步骤 |
| 图片识别 | Tesseract OCR + 图片分析 | 拍照上传即可搜索相关内容 |
| 知识库管理 | JSON 文档加载 + 关键词检索 | 动态扩展知识库 |
| 多轮对话 | 上下文记忆 + Prompt 工程 | 连续追问，逐步深入 |
| 安全提示 | 关键词规则引擎 | 高风险操作自动提醒 |
| 密码保护 | Session 状态管理 | 防止链接未授权访问 |

## 技术架构

```
用户提问 → 关键词检索（知识库） → 检索结果 + Prompt → GLM-4 生成回答
                                      ↑
                              快捷规则引擎（优先匹配）
```

- **RAG 层**：JSON 知识库 → 关键词提取 → 相关性评分 → Top-K 检索
- **LLM 层**：智谱 GLM-4-Flash，Prompt 约束只使用上下文回答
- **OCR 层**：Tesseract（本地）/ 百度 OCR（云端），均为可选
- **安全层**：快捷回答规则引擎 + 访问密码保护

## 快速开始

### 环境要求
- Python 3.10+
- Windows / macOS / Linux

### 启动
```bash
pip install -r requirements.txt
streamlit run afm_rag_streamlit_image.py
```

### 访问密码
部署后请在代码中修改 `APP_PASSWORD` 变量为你自己的密码（默认值为 `change-me`，务必修改）。

## 云端部署（Streamlit Cloud）

### Step 1：创建 GitHub 仓库
1. 注册/登录 [GitHub](https://github.com/)
2. 点击 **New repository**，命名为 `afm-assistant-demo`
3. 选择 **Public**，勾选 **Add a README file**
4. 点击 **Create repository**

### Step 2：上传文件
点击仓库的 **Add file → Upload files**，上传以下文件：

```
afm_rag_streamlit_image.py     # 主程序
requirements.txt               # 依赖清单
quick_answers.json             # 快捷回答规则（安全提示）
demo_knowledge_base.txt        # 脱敏示例知识库
README.md                      # 项目说明
.streamlit/
  └── config.toml              # Streamlit配置
.gitignore                     # Git忽略规则
```

> **注意**：真实知识库文档（操作手册、培训讲义等）不包含在仓库中，已被 `.gitignore` 排除。仓库仅提供脱敏示例数据用于演示。

### Step 3：部署到 Streamlit Cloud
1. 打开 [share.streamlit.io](https://share.streamlit.io/)
2. 用 GitHub 账号登录
3. 点击 **New app**：
   - Repository：选择 `afm-assistant-demo`
   - Branch：`main`
   - Main file path：`afm_rag_streamlit_image.py`
4. 点击 **Deploy**，等待 1-2 分钟
5. 部署完成后获得公开链接，如：
   `https://afm-assistant-demo-xxx.streamlit.app`

### Step 4：分享
将链接和访问密码发送给面试官即可（密码请在代码中自行设置）。

## 知识库说明

| 文件 | 内容 | 说明 |
|------|------|------|
| `demo_knowledge_base.txt` | AFM 通用知识 | 脱敏示例数据，可公开演示 |
| `shujuku/*.txt` | 用户自行放入的真实文档 | 原始知识库（已通过 .gitignore 排除，不上传） |

知识库格式为 JSON 数组：
```json
{
  "id": "唯一ID",
  "source": "来源",
  "title": "标题",
  "content": "内容正文",
  "tags": ["标签1", "标签2"]
}
```

## API Key 配置

在左侧边栏填入智谱 AI API Key 即可启用 GLM-4 优化回答。

获取地址：[智谱开放平台](https://open.bigmodel.cn/)

未填入 Key 时，系统仍可基于知识库检索返回结果（仅不走 LLM 优化）。

## 项目结构

```
AFM仪器助手/
├── afm_rag_streamlit_image.py   # 主程序
├── requirements.txt              # 依赖清单
├── quick_answers.json            # 快捷回答规则（安全提示）
├── demo_knowledge_base.txt       # 脱敏示例知识库
├── .gitignore                    # Git忽略规则
├── .streamlit/
│   └── config.toml               # Streamlit配置
├── shujuku/                      # 真实知识库目录（用户自备，不上传）
├── output/                       # 图片资源（本地，不上传）
└── Tesseract-OCR/                # OCR引擎（本地，不上传）
```

## 技术亮点

1. **RAG + LLM 双层架构** — 检索保证准确性，LLM 保证可读性
2. **Prompt 约束** — 限制模型只使用上下文回答，杜绝幻觉
3. **快捷规则引擎** — 高风险操作（如换探针）自动插入安全提示
4. **多模态输入** — 文字 + 图片 + OCR，覆盖多种使用场景
5. **上下文记忆** — 支持多轮对话，连续追问不丢失上下文
6. **优雅降级** — 无 Tesseract / 无图片时仍可运行，不影响核心问答
7. **密码保护** — 云端部署后防未授权访问
