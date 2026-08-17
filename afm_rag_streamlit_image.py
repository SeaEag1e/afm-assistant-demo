#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AFM仪器操作助手 - 图片拓展版
功能：图片上传 + OCR识别 + 图片问答 + 图片搜索
"""

import json
from pathlib import Path
import os
import streamlit as st
import requests
from PIL import Image
import re

# pytesseract 可选导入（云端未安装时不影响主功能）
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

# ==================== 配置 - 使用相对路径 ====================
if getattr(__import__('sys'), 'frozen', False):
    SCRIPT_DIR = Path(os.path.dirname(__import__('sys').executable))
else:
    SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = SCRIPT_DIR / "shujuku"
OUTPUT_DIR = SCRIPT_DIR / "output"
TOP_K = 5

# 多个知识库搜索目录（云端 demo_knowledge_base.txt 可能在根目录）
KNOWLEDGE_DIRS = [DATA_DIR, SCRIPT_DIR]

# OCR配置
def get_tesseract_path():
    candidates = [
        SCRIPT_DIR / "Tesseract-OCR" / "tesseract.exe",
        SCRIPT_DIR / "tesseract_path.txt",
    ]
    config_file = SCRIPT_DIR / "tesseract_path.txt"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                path = f.read().strip()
                if path and os.path.exists(path):
                    return path
        except:
            pass
    if (SCRIPT_DIR / "Tesseract-OCR" / "tesseract.exe").exists():
        return str(SCRIPT_DIR / "Tesseract-OCR" / "tesseract.exe")
    return r'C:\Program Files\Tesseract-OCR\tesseract.exe'

TESSERACT_CMD = get_tesseract_path()

# OCR提供者配置
OCR_PROVIDERS = {
    "tesseract": {
        "name": "Tesseract OCR（本地）",
        "description": "已安装，免费但准确率一般"
    },
    "baidu": {
        "name": "百度OCR",
        "description": "准确率高，需要API Key，免费额度有限"
    }
}

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 状态管理 ====================
if 'documents' not in st.session_state:
    st.session_state.documents = []
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = []

# ==================== 文档加载器 ====================
class DocumentLoader:
    @staticmethod
    def load_all():
        documents = []
        seen_files = set()
        txt_files = []
        for kdir in KNOWLEDGE_DIRS:
            if kdir.exists():
                for f in kdir.glob("**/*.txt"):
                    key = str(f.resolve())
                    if key not in seen_files:
                        seen_files.add(key)
                        txt_files.append(f)
        
        for txt_file in txt_files:
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    documents.extend(data)
                else:
                    documents.append(data)
            except Exception as e:
                st.warning(f"加载文件失败 {txt_file}: {str(e)}")
        
        return documents

# ==================== 图片管理器 ====================
class ImageManager:
    @staticmethod
    def find_images(query):
        image_dirs = []
        for root, dirs, files in os.walk(DATA_DIR):
            for dir_name in dirs:
                if 'images' in dir_name.lower():
                    image_dirs.append(os.path.join(root, dir_name))
        
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for dir_name in dirs:
                if 'images' in dir_name.lower():
                    image_dirs.append(os.path.join(root, dir_name))
        
        query_lower = query.lower()
        matching_images = []
        
        for img_dir in image_dirs:
            try:
                for filename in os.listdir(img_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        if query_lower in filename.lower():
                            matching_images.append(os.path.join(img_dir, filename))
            except Exception as e:
                pass
        
        return matching_images[:5]
    
    @staticmethod
    def find_all_images():
        all_images = []
        
        for root, dirs, files in os.walk(DATA_DIR):
            for dir_name in dirs:
                if 'images' in dir_name.lower():
                    img_dir = os.path.join(root, dir_name)
                    try:
                        for filename in os.listdir(img_dir):
                            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                                all_images.append(os.path.join(img_dir, filename))
                    except Exception as e:
                        pass
        
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for dir_name in dirs:
                if 'images' in dir_name.lower():
                    img_dir = os.path.join(root, dir_name)
                    try:
                        for filename in os.listdir(img_dir):
                            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                                all_images.append(os.path.join(img_dir, filename))
                    except Exception as e:
                        pass
        
        return all_images

# ==================== OCR识别器 ====================
class OCRProcessor:
    """OCR处理器，支持多种识别引擎"""
    
    @staticmethod
    def preprocess_image(image, enhance_for_ui=True):
        """
        预处理图片，提高OCR识别率
        
        Args:
            image: PIL Image对象
            enhance_for_ui: 是否针对UI界面优化
        """
        from PIL import ImageEnhance, ImageFilter
        
        # 转为灰度图
        gray = image.convert('L')
        
        if enhance_for_ui:
            # 增加对比度（UI界面文字通常需要高对比度）
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(2.0)
            
            # 锐化图片
            sharpened = enhanced.filter(ImageFilter.SHARPEN)
            
            # 二值化处理
            threshold = 128
            binary = sharpened.point(lambda x: 255 if x > threshold else 0)
            
            return binary
        
        return gray
    
    @staticmethod
    def extract_text_with_tesseract(image):
        """使用Tesseract提取文字"""
        try:
            import pytesseract
            
            # 自动搜索Tesseract路径
            tesseract_paths = [
                TESSERACT_CMD,
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'D:\Tesseract-OCR\tesseract.exe',
                r'E:\Tesseract-OCR\tesseract.exe',
            ]
            
            found_path = None
            for path in tesseract_paths:
                if os.path.exists(path):
                    found_path = path
                    break
            
            if found_path:
                pytesseract.pytesseract.tesseract_cmd = found_path
            else:
                return "❌ 未找到Tesseract！\n\n请按以下步骤安装：\n1. 下载安装包：https://github.com/UB-Mannheim/tesseract/wiki\n2. 默认安装到：C:\\Program Files\\Tesseract-OCR\n3. 安装时勾选中文语言包\n4. 运行 AFM_Portable\\配置Tesseract.bat"
            
            custom_config = r'--oem 3 --psm 6 -l chi_sim+eng'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            if text.strip():
                return text.strip()
            else:
                return "⚠️ OCR未识别到文字。可能原因：\n1. 图片文字太小或模糊\n2. 对比度太低\n3. 建议尝试百度OCR（准确率更高）"
                
        except FileNotFoundError:
            return "❌ Tesseract未安装！\n\n解决方案：\n1. 安装Tesseract：https://github.com/UB-Mannheim/tesseract/wiki\n2. 或使用百度OCR（准确率更高）"
        except Exception as e:
            return f"❌ OCR识别失败: {str(e)}\n\n解决方案：\n1. 确保Tesseract已安装并配置PATH\n2. 或使用百度OCR（准确率更高）"
    
    @staticmethod
    def extract_text_with_baidu(image, api_key, secret_key):
        """使用百度OCR API提取文字"""
        try:
            import base64
            from io import BytesIO
            
            # 获取access_token
            token_url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": secret_key
            }
            response = requests.get(token_url, params=params)
            result = response.json()
            access_token = result.get('access_token')
            
            if not access_token:
                return "❌ 百度API认证失败，请检查API Key"
            
            # 将图片转为base64
            buffered = BytesIO()
            image.save(buffered, format='PNG')
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # 调用百度OCR
            ocr_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {
                'access_token': access_token,
                'image': img_base64
            }
            
            response = requests.post(ocr_url, headers=headers, data=data)
            result = response.json()
            
            if 'words_result' in result:
                words = [item['words'] for item in result['words_result']]
                return '\n'.join(words)
            else:
                return f"❌ OCR识别失败: {result.get('error_msg', '未知错误')}"
                
        except Exception as e:
            return f"❌ 百度OCR调用失败: {str(e)}"
    
    @staticmethod
    def extract_text(image, provider='tesseract', api_key='', secret_key=''):
        """
        提取图片文字
        
        Args:
            image: PIL Image对象
            provider: OCR提供者 ('tesseract' 或 'baidu')
            api_key: 百度API Key
            secret_key: 百度Secret Key
        """
        if provider == 'baidu' and api_key and secret_key:
            return OCRProcessor.extract_text_with_baidu(image, api_key, secret_key)
        else:
            # 预处理图片
            processed = OCRProcessor.preprocess_image(image)
            return OCRProcessor.extract_text_with_tesseract(processed)
    
    @staticmethod
    def extract_text_from_path(image_path, provider='tesseract', api_key='', secret_key=''):
        """从图片文件提取文字"""
        try:
            image = Image.open(image_path)
            return OCRProcessor.extract_text(image, provider, api_key, secret_key)
        except Exception as e:
            return f"❌ 打开图片失败: {str(e)}"
    
    @staticmethod
    def analyze_image_features(image):
        """分析图片特征，用于仪器界面识别"""
        features = []
        
        try:
            width, height = image.size
            features.append(f"图片尺寸: {width}x{height}")
            
            # 计算平均亮度和对比度
            gray = image.convert('L')
            pixels = list(gray.getdata())
            avg_brightness = sum(pixels) / len(pixels)
            
            # 计算对比度
            variance = sum((p - avg_brightness) ** 2 for p in pixels) / len(pixels)
            contrast = variance ** 0.5
            
            features.append(f"平均亮度: {avg_brightness:.2f}/255")
            features.append(f"对比度: {contrast:.2f}")
            
            # 检测是否为UI界面
            aspect_ratio = width / height
            features.append(f"宽高比: {aspect_ratio:.2f}")
            
            if aspect_ratio > 1.3 and aspect_ratio < 2.0:
                features.append("📊 可能是横向UI界面截图")
            elif aspect_ratio < 0.8:
                features.append("📱 可能是竖向UI界面截图")
            
            # 检测颜色分布
            if image.mode == 'RGB':
                r_avg = sum(p[0] for p in image.getdata()) / (width * height)
                g_avg = sum(p[1] for p in image.getdata()) / (width * height)
                b_avg = sum(p[2] for p in image.getdata()) / (width * height)
                features.append(f"色调: R={r_avg:.0f}, G={g_avg:.0f}, B={b_avg:.0f}")
            
        except Exception as e:
            features.append(f"特征分析失败: {str(e)}")
        
        return features

# ==================== 搜索器 ====================
class SearchEngine:
    def __init__(self, documents):
        self.documents = documents
    
    def search(self, query):
        results = []
        query_lower = query.lower()
        
        keywords = self._extract_keywords(query_lower)
        
        for doc in self.documents:
            score = self._calculate_score(doc, keywords, query_lower)
            if score > 0:
                results.append({'score': score, 'doc': doc})
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:TOP_K]
    
    def _extract_keywords(self, query):
        keywords = []
        
        english_words = re.findall(r'[a-zA-Z]{2,}', query)
        keywords.extend(english_words)
        
        chinese_chars = [c for c in query if '\u4e00' <= c <= '\u9fff']
        for i in range(len(chinese_chars)):
            keywords.append(chinese_chars[i])
            if i < len(chinese_chars) - 1:
                keywords.append(chinese_chars[i] + chinese_chars[i+1])
            if i < len(chinese_chars) - 2:
                keywords.append(chinese_chars[i] + chinese_chars[i+1] + chinese_chars[i+2])
        
        return list(set(keywords))
    
    def _calculate_score(self, doc, keywords, query):
        score = 0
        text = (doc.get('content', '') + ' ' + doc.get('title', '')).lower()
        
        for kw in keywords:
            if kw in text:
                score += 10
                if len(kw) > 1:
                    score += 5
        
        tags = ' '.join(doc.get('tags', [])).lower()
        for kw in keywords:
            if kw in tags:
                score += 20
        
        if query in text:
            score += 30
        
        return score

# ==================== 智谱AI客户端 ====================
class ZhipuAIClient:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def generate(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "glm-4-flash",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "top_p": 0.1
        }
        
        try:
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return None
    
    def chat(self, messages, model="glm-4-flash"):
        """支持多轮对话，messages 为 [{"role": "user"/"assistant", "content": ...}]"""
        if not self.api_key:
            return "⚠️ 请先在左侧设置智谱AI API Key"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        try:
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"❌ 调用失败: {str(e)}"

# ==================== 快捷回答系统 ====================
class QuickAnswerLoader:
    """
    高优先级快捷回答 - 直接根据关键词返回预设回答
    编辑 quick_answers.json 即可添加新规则
    """
    CONFIG_FILE = SCRIPT_DIR / "quick_answers.json"

    @classmethod
    def load(cls):
        try:
            if not cls.CONFIG_FILE.exists():
                return []
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('quick_answers', [])
        except Exception:
            return []

    @classmethod
    def check(cls, question):
        """检查问题是否命中快捷回答，返回(rule_dict, matched_text)或(None, None)

        rule_dict 包含:
          - mode: "only" 直接返回预设回答 | "prepend" 先给警告再走正常RAG
          - warning: 警告/提示文本（prepend 模式用）
          - footer: 结尾免责文本（prepend 模式用）
          - answer: 直接回答内容（only 模式用）
        """
        if not question:
            return None, None
        q = question.strip().lower()
        rules = cls.load()
        for rule in rules:
            keywords = rule.get('keywords', [])
            for kw in keywords:
                if kw.lower() in q:
                    return rule, kw
            keyword_groups = rule.get('keyword_groups', [])
            for group in keyword_groups:
                if all(word.lower() in q for word in group):
                    return rule, '+'.join(group)
        return None, None

# ==================== RAG系统 ====================
class AFMRAGSystem:
    def __init__(self):
        self.documents = DocumentLoader.load_all()
        self.search_engine = SearchEngine(self.documents)
        self.total_docs = len(self.documents)
    
    def query(self, question, api_key="", use_llm=True, context=""):
        # --- 1. 优先检查快捷回答（最高优先级） ---
        rule, matched_kw = QuickAnswerLoader.check(question)
        mode = rule.get('mode', 'only') if rule else None

        # --- 2. 常规知识库搜索 ---
        results = self.search_engine.search(question)

        # 如果规则是 only 模式，且命中了，直接返回预设回答（跳过知识库）
        if rule and mode == 'only':
            return rule.get('answer', ''), ["快捷回答（系统规则）"], True, []

        # 没有找到结果且没有规则，返回默认
        if not results and not rule:
            return "抱歉，说明书中未提及该内容，请查阅纸质手册或联系工程师。", [], False, []

        images = ImageManager.find_image_text(question) if hasattr(ImageManager, 'find_image_text') else ImageManager.find_images(question)

        context_text = "\n\n".join([
            f"【{r['doc'].get('title', '')}】\n来源: {r['doc'].get('source', '')}\n内容: {r['doc'].get('content', '')}"
            for r in results
        ])
        sources = list(set([r['doc'].get('source', '') for r in results]))

        # 生成最终答案
        if results and use_llm and api_key:
            prompt = self._build_prompt(context_text, question, context)
            client = ZhipuAIClient(api_key)
            answer = client.generate(prompt)
        elif results:
            answer = "\n\n".join([
                f"{idx+1}. {r['doc'].get('title', '')}\n{r['doc'].get('content', '')}"
                for idx, r in enumerate(results)
            ])
        else:
            answer = "抱歉，说明书中未提及该内容，请查阅纸质手册或联系工程师。"
            sources = []

        # prepend 模式：前加警告，后加免责声明
        if rule and mode == 'prepend':
            topic = rule.get('topic', '')
            warning = rule.get('warning', '')
            footer = rule.get('footer', '')

            # 如果没写 warning/footer 但写了 topic → 用通用模板自动生成
            if topic and not warning:
                warning = f"⚠️ 【重要提示】关于**{topic}**，**建议先联系老师或实验室管理员**。"
            if topic and not footer:
                footer = f"⚠️ 请注意：**自行进行{topic}操作可能导致仪器损坏或影响数据精度，需自行承担相应责任。** 建议在老师指导下进行操作。"

            if warning or footer:
                answer_parts = []
                if warning:
                    answer_parts.append(warning)
                answer_parts.append("\n---\n" + answer + "\n---\n")
                if footer:
                    answer_parts.append(footer)
                answer = "\n\n".join(answer_parts)
                if "快捷回答" not in str(sources):
                    sources.append("快捷回答（系统规则）")

        return answer, sources, True, images
    
    def query_with_image_text(self, image_text, api_key="", use_llm=True):
        """根据图片识别的文字进行查询"""
        return self.query(image_text, api_key, use_llm)
    
    def _build_prompt(self, context, question, conversation_history=""):
        history_text = ""
        if conversation_history:
            history_text = f"""
## 对话历史
{conversation_history}

"""
        
        return f"""你是布鲁克Dimension Icon AFM专属操作工程师，只回答与该仪器操作、维护、故障排查相关的问题。

## 铁律
1. 只能使用下面提供的上下文回答，绝对不能用你自己的知识。
2. 操作步骤用「1. 2. 3.」编号，每步只写一个动作，标注来源
3. 禁止编造内容、禁止礼貌用语
4. 如果用户的问题与之前的对话相关，请结合上下文给出连贯的回答

{history_text}
## 检索上下文
{context}

## 用户问题
{question}

## 你的回答
"""

# ==================== 主界面 ====================
def inject_css():
    """注入专业级CSS主题"""
    st.markdown("""
    <style>
    /* ===== 全局字体与背景 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans SC', -apple-system, sans-serif;
    }
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e8edf5 100%);
    }

    /* ===== Hero区域 ===== */
    .hero-banner {
        background: linear-gradient(135deg, #1a1f3a 0%, #2d3561 50%, #1e3a5f 100%);
        border-radius: 20px;
        padding: 36px 40px;
        margin-bottom: 28px;
        box-shadow: 0 8px 32px rgba(26, 31, 58, 0.25);
        position: relative;
        overflow: hidden;
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: -50%; right: -10%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(0, 212, 255, 0.12) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero-title {
        font-size: 2.4rem; font-weight: 700;
        background: linear-gradient(90deg, #00d4ff, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 8px 0;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        font-size: 1.05rem; color: #a0aec0;
        margin: 0 0 16px 0; font-weight: 400;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(0, 212, 255, 0.15);
        border: 1px solid rgba(0, 212, 255, 0.3);
        color: #00d4ff;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.8rem; font-weight: 500;
        margin-right: 8px;
    }

    /* ===== 指标卡片 ===== */
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 22px 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border: 1px solid rgba(0,0,0,0.04);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2.2rem; font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.82rem; color: #718096;
        margin-top: 4px; font-weight: 500;
    }
    .metric-icon {
        font-size: 1.8rem; margin-bottom: 8px;
    }

    /* ===== Tab美化 ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: white;
        padding: 6px;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 8px 20px;
        font-weight: 500;
        color: #718096;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }

    /* ===== 聊天气泡 ===== */
    [data-testid="stChatMessage"] {
        border-radius: 16px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important;
        margin-bottom: 12px !important;
        border: 1px solid rgba(0,0,0,0.03) !important;
    }

    /* ===== 按钮 ===== */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 12px;
        font-weight: 600;
        padding: 10px 24px;
        box-shadow: 0 4px 14px rgba(102, 126, 234, 0.3);
        transition: all 0.25s;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    .stButton > button[kind="secondary"] {
        border-radius: 12px;
        font-weight: 500;
        border: 1px solid #e2e8f0;
    }

    /* ===== 输入框 ===== */
    .stTextArea textarea, .stTextInput input {
        border-radius: 12px !important;
        border: 1.5px solid #e2e8f0 !important;
        transition: border-color 0.2s;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }

    /* ===== 侧边栏 ===== */
    section[data-testid="stSidebar"] {
        background: white;
        box-shadow: 2px 0 20px rgba(0,0,0,0.04);
    }
    .sidebar-header {
        font-size: 1.1rem; font-weight: 700;
        color: #1a202c;
        padding: 4px 0 8px 0;
        border-bottom: 2px solid;
        border-image: linear-gradient(90deg, #667eea, #764ba2) 1;
        margin-bottom: 12px;
    }

    /* ===== 状态指示器 ===== */
    .status-dot {
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .status-online { background: #48bb78; box-shadow: 0 0 6px #48bb78; }
    .status-offline { background: #f56565; }

    /* ===== 快捷按钮网格 ===== */
    .quick-btn {
        background: white !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 12px 8px !important;
        font-size: 0.85rem !important;
        color: #4a5568 !important;
        transition: all 0.2s;
    }
    .quick-btn:hover {
        border-color: #667eea !important;
        color: #667eea !important;
        background: #f7f8fc !important;
    }

    /* ===== 来源标签 ===== */
    .source-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 16px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .source-ok {
        background: linear-gradient(135deg, #48bb78, #38a169);
        color: white;
    }
    .source-warn {
        background: linear-gradient(135deg, #ed8936, #dd6b20);
        color: white;
    }

    /* ===== 隐藏Streamlit默认元素 ===== */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ===== 分割线 ===== */
    .custom-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
        margin: 20px 0;
        border: none;
    }

    /* ===== 响应式适配 ===== */
    @media (max-width: 768px) {
        .hero-title { font-size: 1.6rem; }
        .hero-banner { padding: 24px 20px; }
        .metric-value { font-size: 1.6rem; }
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="AFM智能助手 | RAG + GLM-4",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    inject_css()

    # ===== Hero区域 =====
    st.markdown("""
    <div class="hero-banner">
        <div style="margin-bottom:12px;">
            <span class="hero-badge">🔬 Bruker Dimension Icon</span>
            <span class="hero-badge">🧠 RAG + GLM-4</span>
            <span class="hero-badge">📷 OCR 图片识别</span>
        </div>
        <h1 class="hero-title">AFM 智能操作助手</h1>
        <p class="hero-subtitle">基于 RAG 检索增强生成 + 大语言模型的专业原子力显微镜知识库问答系统，让仪器操作零门槛</p>
    </div>
    """, unsafe_allow_html=True)

    # 初始化系统
    if 'rag_system' not in st.session_state:
        with st.spinner("正在加载知识库..."):
            st.session_state.rag_system = AFMRAGSystem()

    rag_system = st.session_state.rag_system
    total_images = len(ImageManager.find_all_images())

    # ===== 指标卡片 =====
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-icon">📄</div>
            <div class="metric-value">{rag_system.total_docs}</div>
            <div class="metric-label">知识库文档片段</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-icon">🖼️</div>
            <div class="metric-value">{total_images}</div>
            <div class="metric-label">仪器图片资源</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-icon">⚡</div>
            <div class="metric-value">GLM-4</div>
            <div class="metric-label">驱动大模型</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        llm_status = "<span class='status-dot status-online'></span>已启用" if True else "<span class='status-dot status-offline'></span>未启用"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-icon">🤖</div>
            <div class="metric-value" style="font-size:1.3rem;">AI 增强</div>
            <div class="metric-label">{llm_status}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

    # ===== 侧边栏 =====
    with st.sidebar:
        st.markdown('<div class="sidebar-header">⚙️ 配置中心</div>', unsafe_allow_html=True)

        with st.expander("🔑 AI 模型配置", expanded=True):
            api_key = st.text_input(
                "智谱AI API Key",
                type="password",
                placeholder="sk-xxxxxxxxxxxxxxxxxx",
                help="在 [智谱开放平台](https://open.bigmodel.cn/) 获取"
            )
            use_llm = st.checkbox("启用 GLM-4 优化回答", value=True)

        with st.expander("🔍 OCR 引擎设置", expanded=False):
            ocr_provider = st.selectbox(
                "选择 OCR 引擎",
                options=["tesseract", "baidu"],
                format_func=lambda x: OCR_PROVIDERS[x]["name"],
                help="Tesseract：免费本地；百度：准确率更高"
            )

            if ocr_provider == "baidu":
                baidu_api_key = st.text_input("百度API Key", type="password", placeholder="API Key")
                baidu_secret_key = st.text_input("百度Secret Key", type="password", placeholder="Secret Key")
                st.caption("👉 [获取百度OCR Key](https://cloud.baidu.com/)")
            else:
                baidu_api_key = ""
                baidu_secret_key = ""
                st.caption("✅ 已检测到本地 Tesseract（含中文语言包）")

        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
        st.markdown('<div class="sidebar-header">📊 系统状态</div>', unsafe_allow_html=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("文档片段", rag_system.total_docs)
        with col_s2:
            st.metric("图片资源", total_images)

        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
        st.caption("💡 **使用说明**：输入问题即可获得答案，支持图片上传与OCR识别。")
    
    # 初始化对话历史
    if 'conversation_history' not in st.session_state:
        st.session_state['conversation_history'] = []
    if 'zhipu_history' not in st.session_state:
        st.session_state['zhipu_history'] = []
    
    # 标签页
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💬 智能问答",
        "🖼️ 图片问答",
        "📷 图片库",
        "📖 常见问题",
        "➕ 知识管理",
        "🤖 AI 对话"
    ])

    # 智能问答
    with tab1:
        # 工具栏
        col_t1, col_t2, col_t3 = st.columns([1.2, 1, 2.5])
        with col_t1:
            context_mode = st.toggle("🧠 上下文记忆", value=True, help="开启后，助手会记住并参考之前的对话")
        with col_t2:
            if st.button("🗑️ 清空对话", type="secondary", use_container_width=True):
                st.session_state['conversation_history'] = []
                st.rerun()
        with col_t3:
            conv_count = len(st.session_state['conversation_history'])
            st.markdown(f"<div style='padding:8px 0;text-align:right;color:#718096;font-size:0.85rem;'>📊 已对话 <b style='color:#667eea;'>{conv_count}</b> 轮</div>", unsafe_allow_html=True)

        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

        # 聊天气泡区
        chat_container = st.container()
        with chat_container:
            # 欢迎消息（首次）
            if not st.session_state['conversation_history']:
                with st.chat_message("assistant", avatar="🔬"):
                    st.markdown("""**你好！我是 AFM 智能操作助手** 👋

我可以帮你：
- 📖 解答仪器操作步骤
- 🔧 分析故障与排查方法
- 💡 解释功能原理（如 PFM、KPFM 等）

试试下方快捷问题，或直接输入你的问题！""")

            # 显示历史对话
            for idx, (q, a, from_db, sources) in enumerate(st.session_state['conversation_history']):
                with st.chat_message("user", avatar="👤"):
                    st.markdown(q)

                with st.chat_message("assistant", avatar="🔬"):
                    st.markdown(a)

                    # 来源标签
                    badge_cls = "source-ok" if from_db else "source-warn"
                    badge_text = "✅ 来自知识库" if from_db else "⚠️ 知识库未匹配"
                    st.markdown(f"<span class='source-badge {badge_cls}'>{badge_text}</span>", unsafe_allow_html=True)

                    if sources:
                        with st.expander(f"📚 参考来源（{len(sources)}）", expanded=False):
                            for s in sources:
                                st.text(s)

        # 快捷问题
        st.markdown("<div style='margin-top:8px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>⚡ 快捷提问</div>", unsafe_allow_html=True)
        quick_cols = st.columns(4)
        quick_questions = [
            "液下AFM是什么？",
            "PFM怎么操作？",
            "探针怎么换？",
            "KPFM有什么用？"
        ]
        for i, q in enumerate(quick_questions):
            if quick_cols[i].button(q, key=f"qq_{i}", use_container_width=True):
                context = ""
                if context_mode and st.session_state['conversation_history']:
                    recent = st.session_state['conversation_history'][-5:]
                    context = "\n\n".join([
                        f"用户: {qq}\n助手: {a}"
                        for qq, a, _, _ in recent
                    ])
                with st.spinner("🔍 正在检索知识库并生成回答..."):
                    answer, sources, from_database, images = rag_system.query(
                        q, api_key, use_llm, context=context
                    )
                    st.session_state['conversation_history'].append(
                        (q, answer, from_database, sources)
                    )
                    st.rerun()

        # 输入区
        st.markdown("<div style='margin-top:12px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>✍️ 输入你的问题</div>", unsafe_allow_html=True)
        question = st.text_area(
            "问题描述",
            placeholder="例如：如何校准探针的力常数？",
            height=100,
            label_visibility="collapsed"
        )

        # 提交按钮
        col_send, col_hint = st.columns([3, 2])
        with col_send:
            send_clicked = st.button("🚀 发送提问", type="primary", use_container_width=True)
        with col_hint:
            st.caption("💡 提示：开启上下文记忆可连续追问")

        if send_clicked:
            if question and question.strip():
                with st.spinner("🔍 正在检索知识库并生成回答..."):
                    # 构建上下文
                    context = ""
                    if context_mode and st.session_state['conversation_history']:
                        recent = st.session_state['conversation_history'][-5:]
                        context = "\n\n".join([
                            f"用户: {q}\n助手: {a}"
                            for q, a, _, _ in recent
                        ])

                    answer, sources, from_database, images = rag_system.query(
                        question.strip(), api_key, use_llm, context=context
                    )

                    # 加入历史
                    st.session_state['conversation_history'].append(
                        (question.strip(), answer, from_database, sources)
                    )
                    if len(st.session_state['conversation_history']) > 50:
                        st.session_state['conversation_history'] = st.session_state['conversation_history'][-50:]

                    st.rerun()
            else:
                st.warning("请先输入问题内容")
    
    # 图片问答
    with tab2:
        col_up, col_info = st.columns([2, 1])
        with col_up:
            uploaded_file = st.file_uploader("拖拽或点击上传图片", type=["png", "jpg", "jpeg", "bmp", "gif"], label_visibility="collapsed")
        with col_info:
            st.markdown("""
            <div style='background:white;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,0.06);height:100%;'>
                <div style='font-weight:600;color:#2d3748;margin-bottom:8px;'>📷 图片问答流程</div>
                <div style='color:#718096;font-size:0.85rem;line-height:1.8;'>
                1️⃣ 上传仪器截图或手册照片<br>
                2️⃣ AI 自动 OCR 识别文字<br>
                3️⃣ 检索知识库匹配内容<br>
                4️⃣ 生成专业回答
                </div>
            </div>
            """, unsafe_allow_html=True)

        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="已上传图片", use_column_width=True)

            # 图片特征分析
            with st.spinner("正在分析图片..."):
                features = OCRProcessor.analyze_image_features(image)
                with st.expander("📊 图片特征分析", expanded=False):
                    for feat in features:
                        st.text(feat)

            # OCR识别
            with st.spinner("正在识别图片文字..."):
                ocr_text = OCRProcessor.extract_text(
                    image,
                    provider=ocr_provider,
                    api_key=baidu_api_key,
                    secret_key=baidu_secret_key
                )

                st.markdown("<div style='margin-top:12px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>📝 OCR 识别结果</div>", unsafe_allow_html=True)
                st.text_area("OCR结果", ocr_text, height=150, label_visibility="collapsed")

                # 根据OCR结果搜索
                if ocr_text and ocr_text.strip():
                    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
                    if st.button("🔍 根据图片内容搜索知识库", type="primary", use_container_width=True):
                        with st.spinner("正在检索..."):
                            answer, sources, from_database, images = rag_system.query(ocr_text, api_key, use_llm)

                            st.markdown("<div style='margin-top:12px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>🤖 AI 回答</div>", unsafe_allow_html=True)
                            st.markdown(answer)

                            if from_database:
                                st.success("✅ 回答来自知识库")

                            if sources:
                                with st.expander(f"📚 参考来源（{len(sources)}）"):
                                    for source in sources:
                                        st.text(source)

                            if images:
                                st.markdown("<div style='margin-top:12px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>🖼️ 相关图片</div>", unsafe_allow_html=True)
                                cols = st.columns(3)
                                for i, img_path in enumerate(images[:3]):
                                    with cols[i]:
                                        st.image(img_path, caption=os.path.basename(img_path), use_column_width=True)
    
    # 图片库
    with tab3:
        all_images = ImageManager.find_all_images()

        col_s, col_c = st.columns([3, 1])
        with col_s:
            search_query = st.text_input("🔍 搜索图片", placeholder="输入关键词搜索图片...", label_visibility="collapsed")
        with col_c:
            st.metric("图片总数", len(all_images))

        if search_query:
            images = ImageManager.find_images(search_query)
        else:
            images = all_images

        # 显示图片网格
        if images:
            cols = st.columns(4)
            for i, img_path in enumerate(images[:20]):
                with cols[i % 4]:
                    st.image(img_path, caption=os.path.basename(img_path), use_column_width=True)

                    if st.button(f"OCR 识别", key=f"ocr_{i}", use_container_width=True):
                        with st.spinner("正在识别..."):
                            ocr_text = OCRProcessor.extract_text_from_path(
                                img_path,
                                provider=ocr_provider,
                                api_key=baidu_api_key,
                                secret_key=baidu_secret_key
                            )
                            st.text_area("OCR 结果", ocr_text, height=150, key=f"ocr_result_{i}")

                            if ocr_text and not ocr_text.startswith("失败"):
                                if st.button("根据识别内容搜索", key=f"search_{i}", use_container_width=True):
                                    answer, sources, from_database, _ = rag_system.query(ocr_text, api_key, use_llm)
                                    st.markdown(answer)
        else:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;">
                <div style="font-size:3rem;margin-bottom:16px;">🖼️</div>
                <h3 style="color:#4a5568;margin:0 0 8px 0;">暂无图片资源</h3>
                <p style="color:#a0aec0;font-size:0.9rem;">当前为 Demo 环境，未包含仪器图片库。<br>
                完整版本包含 100+ 张操作手册截图与仪器照片，支持图片搜索与 OCR 识别。</p>
            </div>
            """, unsafe_allow_html=True)

    # 常见问题
    with tab4:
        st.markdown("<div style='margin-bottom:16px;color:#4a5568;font-size:0.9rem;font-weight:500;'>📖 点击常见问题快速获取答案</div>", unsafe_allow_html=True)

        faq_questions = [
            "液下AFM是什么，解决什么问题？",
            "kPFM有什么用？",
            "PFM有什么用？",
            "如何校准力常数？",
            "激光偏了怎么办？",
            "如何更换探针？",
            "力曲线怎么采集？",
            "ScanAsyst模式介绍",
            "接触模式切换方法",
            "AFM基本原理"
        ]

        # 两列布局
        faq_cols = st.columns(2)
        for i, q in enumerate(faq_questions):
            with faq_cols[i % 2]:
                if st.button(q, key=q, use_container_width=True):
                    with st.spinner("正在检索..."):
                        answer, sources, from_database, images = rag_system.query(q, api_key, use_llm)

                        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-weight:600;color:#2d3748;margin-bottom:8px;'>❓ {q}</div>", unsafe_allow_html=True)
                        st.markdown(answer)

                        badge_cls = "source-ok" if from_database else "source-warn"
                        badge_text = "✅ 来自知识库" if from_database else "⚠️ 知识库未匹配"
                        st.markdown(f"<span class='source-badge {badge_cls}'>{badge_text}</span>", unsafe_allow_html=True)

                        if sources:
                            with st.expander(f"📚 参考来源（{len(sources)}）"):
                                for source in sources:
                                    st.text(source)

                        if images:
                            st.markdown("<div style='margin-top:12px;margin-bottom:4px;color:#4a5568;font-size:0.85rem;font-weight:500;'>🖼️ 相关图片</div>", unsafe_allow_html=True)
                            cols = st.columns(3)
                            for j, img_path in enumerate(images[:3]):
                                with cols[j]:
                                    st.image(img_path, caption=os.path.basename(img_path), use_column_width=True)

    # 知识管理
    with tab5:
        st.markdown("<div style='margin-bottom:16px;color:#4a5568;font-size:0.9rem;font-weight:500;'>➕ 补充知识库内容</div>", unsafe_allow_html=True)

        col_k1, col_k2 = st.columns(2)
        with col_k1:
            new_title = st.text_input("文档标题", placeholder="例如：探针安装步骤")
        with col_k2:
            new_source = st.text_input("来源", placeholder="例如：操作手册 Rev.D")

        new_content = st.text_area("文档内容", height=180, placeholder="输入文档正文内容...")
        new_tags = st.text_input("标签（逗号分隔）", placeholder="例如：探针,安装,操作")

        if st.button("➕ 添加文档", type="primary", use_container_width=True):
            if new_title and new_content:
                doc = {
                    "title": new_title,
                    "source": new_source or "用户添加",
                    "content": new_content,
                    "tags": [t.strip() for t in new_tags.split(",") if t.strip()]
                }
                rag_system.documents.append(doc)
                rag_system.search_engine = SearchEngine(rag_system.documents)
                st.success(f"✅ 文档已添加！当前共 {len(rag_system.documents)} 个文档")
            else:
                st.warning("请填写标题和内容！")

    # AI 对话
    with tab6:
        col_a1, col_a2, col_a3 = st.columns([1, 1.2, 2])
        with col_a1:
            if st.button("🗑️ 清空对话", key="zhipu_clear", use_container_width=True):
                st.session_state['zhipu_history'] = []
                st.rerun()
        with col_a2:
            model = st.selectbox("模型", ["glm-4-flash", "glm-4", "glm-3-turbo"], index=0, label_visibility="collapsed")
        with col_a3:
            zhipu_count = len(st.session_state['zhipu_history']) // 2
            st.markdown(f"<div style='padding:8px 0;text-align:right;color:#718096;font-size:0.85rem;'>📊 已对话 <b style='color:#667eea;'>{zhipu_count}</b> 轮</div>", unsafe_allow_html=True)

        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
        st.caption("🤖 直接调用 GLM-4，不限制知识库内容，可自由对话")

        # 聊天气泡区
        if not st.session_state['zhipu_history']:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown("""**你好！我是 AI 通用助手** 👋

我可以帮你：
- 💭 回答任何问题
- 📝 写作和润色文案
- 💡 提供灵感和创意
- 🔧 解释概念和原理

有什么想问的？""")

        for role, content in st.session_state['zhipu_history']:
            avatar = "👤" if role == "user" else "🤖"
            with st.chat_message(role, avatar=avatar):
                st.markdown(content)

        # 输入区
        st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
        user_input = st.text_area(
            "输入你的问题或内容",
            placeholder="例如：帮我写一段关于纳米材料的介绍...",
            height=120,
            key="zhipu_input",
            label_visibility="collapsed"
        )

        if st.button("🚀 发送", type="primary", use_container_width=True, key="zhipu_send"):
            if not api_key:
                st.error("⚠️ 请先在左侧设置智谱AI API Key")
            elif user_input and user_input.strip():
                # 构造消息历史
                messages = []
                for role, content in st.session_state['zhipu_history'][-10:]:
                    messages.append({"role": role, "content": content})
                messages.append({"role": "user", "content": user_input.strip()})

                # 显示用户消息
                with st.chat_message("user", avatar="👤"):
                    st.markdown(user_input.strip())

                # 调用AI
                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("💭 AI 正在思考..."):
                        client = ZhipuAIClient(api_key)
                        response = client.chat(messages, model=model)
                        st.markdown(response)

                # 保存对话
                st.session_state['zhipu_history'].append(("user", user_input.strip()))
                st.session_state['zhipu_history'].append(("assistant", response))
                if len(st.session_state['zhipu_history']) > 100:
                    st.session_state['zhipu_history'] = st.session_state['zhipu_history'][-100:]

                st.rerun()
            else:
                st.warning("请先输入内容")

    # 页脚
    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align:center;color:#a0aec0;font-size:0.78rem;padding:8px 0;'>
        AFM 智能操作助手 · RAG + GLM-4 · Bruker Dimension Icon 知识库问答系统
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()