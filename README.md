# AFM 智能操作助手

基于 RAG + GLM-4 的原子力显微镜知识库问答系统。把仪器操作文档变成一个能对话的助手，输入问题直接得到操作步骤，不用翻几百页手册。

## 为什么做这个

实验室有一台 AFM，操作手册很厚，新同学上手时经常找不到对应的内容。培训课听完后也容易忘。这个项目就是把操作文档喂进知识库，用自然语言提问就能查到答案，遇到高风险操作（换针、调焦进针）还会自动弹安全提醒。

## 功能

- **智能问答**：输入问题 → 检索知识库 → GLM-4 生成回答，支持多轮追问
- **图片识别**：上传仪器截图，OCR 提取文字后自动检索
- **安全规则引擎**：换针、调焦进针等高风险操作自动插入警示，通过 `quick_answers.json` 配置，不改代码就能加新规则
- **密码保护**：部署到云端后防止未授权访问

## 技术栈

- Streamlit（前端）
- 智谱 GLM-4-Flash（LLM，通过 REST API 调用）
- TF-IDF + 关键词混合检索（没上向量库，文档量小的时候精确检索更靠谱）
- Tesseract / 百度 OCR（可选，不做 OCR 也能正常问答）

## 快速开始

```bash
pip install -r requirements.txt
streamlit run afm_rag_streamlit_image.py
```

浏览器打开 `http://localhost:8501`。

没填 API Key 也能用，只是不走 LLM 优化，直接返回检索到的原文。GLM-4-Flash 每月免费 100 万 tokens，去 [智谱开放平台](https://open.bigmodel.cn/) 注册就行。

## 访问密码

代码里 `APP_PASSWORD` 默认是 `change-me`，部署前务必改成自己的密码。

## 部署到 Streamlit Cloud

1. 把仓库文件上传到 GitHub
2. 打开 [share.streamlit.io](https://share.streamlit.io/)，用 GitHub 登录
3. New app → 选仓库 → main 分支 → 入口文件 `afm_rag_streamlit_image.py`
4. Deploy，等一两分钟拿到公开链接
5. 把链接和密码发给需要的人

仓库里只包含脱敏示例数据 `demo_knowledge_base.txt`，真实操作文档不上传（已通过 `.gitignore` 排除）。

## 知识库格式

知识库是 JSON 数组，每条文档长这样：

```json
{
  "id": "唯一ID",
  "source": "来源",
  "title": "标题",
  "content": "内容正文",
  "tags": ["标签1", "标签2"]
}
```

把自己的文档放到 `shujuku/` 目录下，重启就自动加载。也可以在网页的「添加文档」Tab 里直接追加。

## 安全规则配置

`quick_answers.json` 里目前有两条规则：

- **换针/更换探针** — 命中关键词后先提醒联系老师，再给正常回答
- **调焦/聚焦/进针** — 同上，提醒调焦不当可能损坏仪器

想加新规则，往 `quick_answers` 数组里追加一条就行：

```json
{
  "mode": "prepend",
  "topic": "激光安全",
  "keywords": ["开激光", "laser on"],
  "keyword_groups": [["激光", "开启"]]
}
```

`mode` 有两种：`prepend`（先警示再正常回答）和 `only`（只给警示，跳过检索）。`warning` 和 `footer` 不写的话会根据 `topic` 自动生成。

## 项目结构

```
├── afm_rag_streamlit_image.py   # 主程序
├── requirements.txt
├── quick_answers.json            # 安全规则配置
├── demo_knowledge_base.txt       # 脱敏示例知识库
├── .streamlit/config.toml
├── .gitignore
├── shujuku/                      # 真实知识库（自备，不上传）
├── output/                       # 图片资源（本地，不上传）
└── Tesseract-OCR/                # OCR 引擎（本地，不上传）
```
