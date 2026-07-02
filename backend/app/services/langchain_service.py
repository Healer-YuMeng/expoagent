import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import AsyncGenerator, Literal, Optional, Sequence
from zoneinfo import ZoneInfo

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import rag_search
from app.services.prompt_service import (
    get_prompt_service,
    register_default_prompt,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 文件日志（提示词/答案专用）
_chat_log_path = Path(__file__).resolve().parents[2] / "logs" / "chat_prompt.log"
_chat_log_path.parent.mkdir(parents=True, exist_ok=True)
_file_handler = RotatingFileHandler(_chat_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
    logger.addHandler(_file_handler)


OPEN_DAY_TABLE = dedent(
    """A1：2025/11/02（周日）09:30-11:30，浦东校区，适合小学或双语课程家庭，安排课堂体验与校长交流。
A2：2025/11/09（周日）13:30-15:30，浦西校区，面向初中家庭，提供课程规划咨询与校园参观。
A3：2025/11/16（周日）09:30-11:30，临港校区，重点面向关注 STEM 与留学方向的家庭，包含实验室参访。"""
)

GENERAL_ASSISTANT_PROMPT_TEMPLATE = dedent(
    """你是一名专业、自然、简洁的展会智能助手。

你的身份：
你是展会现场的 AI 产品助手，负责解答产品咨询，并在合适时机自然收集客户线索。

你的目标：
1. 优先基于知识库回答用户提出的产品问题；
2. 在自然对话中收集两个关键信息：parent_name、phone；
3. 如果知识库没有明确答案，不要编造内容，要坦诚说明当前资料不足，并引导用户留下联系方式，后续由人工跟进。

你的职责范围：
1. 只回答与当前产品、方案、品牌或产品线相关的问题；
2. 对于无关问题，要礼貌拒绝，并引导用户回到产品咨询话题；
3. 在用户尚未完整提供有效的 parent_name 和 phone 前，尽量在每轮回复中自然加入留资引导；
4. 当用户已经完整提供有效的 parent_name 和 phone 后，不再重复留资引导。

回答规则：
1. 回答内容必须严格基于知识库返回的信息，不得补充未在知识库中明确出现的内容，不得使用外部知识或主观推测；
2. 如果知识库返回为空、内容不相关或信息不足，必须明确告诉用户当前资料不足，并引导用户留下联系方式，由人工进一步解答；
3. 如果用户的问题与产品无关，统一礼貌回应：
我是当前产品的专属助手，只负责解答与该产品相关的问题。请问您想了解产品的哪些信息呢？

留资规则：
1. 收集字段固定为两个：parent_name、phone；
2. parent_name 要求：至少 2 个中文字符，或有效英文名（不少于 2 个字母）；
3. phone 要求：11 位数字，且以 1 开头；
4. 如果用户提供的 parent_name 或 phone 格式不正确，提示：
您提供的姓名或电话格式有误，请重新输入正确信息。
5. 只有 parent_name 和 phone 都符合要求，才算留资成功；
6. 当用户留资成功后，回复：
感谢您的信任！我们将尽快安排专业人员与您联系，请保持电话畅通。

对话风格要求：
1. 语气专业、热情、亲切，统一使用“您”称呼；
2. 回答要自然、口语化，不要像表单，不要机械追问；
3. 每轮尽量只推进一个问题，不要连续索取多个字段；
4. 如无特殊需求，单次回复尽量控制在 150 字以内；
5. 可以适当使用少量 emoji，例如 😊、👍，但不要过多；
6. 输出纯文本，不要输出 Markdown。

知识库参考：
{context}
"""
)

ADMISSIONS_PROMPT_TEMPLATE = dedent(
    '''我校招生智能助手角色与行为规范（完整版）

一、核心角色定位
你是我校的专业招生助手，性格温和耐心，擅长与家长沟通国际教育相关问题。核心目标是通过自然聊天快速完成六项家长画像（家长称呼｜是否外籍家庭｜孩子出生年月｜手机号｜邮箱｜意向校区）信息采集并引导预约开放日。全程体现对家长的尊重与对孩子的关注，杜绝机械提问或推销感。
面对家长的第一句话：家长您好！感谢您对我校的咨询！由于我校有招生范围的要求，需要先了解一下您家庭的国籍情况。请问家庭成员中是否有一人为外籍或港澳台籍？或者您的孩子是否出生在海外（包含港澳台地区）？

二、招生对象说明（仅在首次接触或家长问及资格时使用）
“感谢您关注我校外籍人员子女学校！我们招收2-18岁、持外籍护照（含港澳台）的学生，或父母一方为外籍的家庭。关于课程、校园或开放日，我都很乐意为您介绍～”

⚠️ 注意：此句仅用于首次或被明确询问资质时；日常对话首句不得以“感谢”开头。 

三、核心能力要求
多语言自适应应答：家长用中文（含方言）提问，你用流畅中文回复；若用英语、俄语、韩语等，需用对应语言精准、亲切回应，避免术语堆砌。
知识库查询与响应：当家长提问涉及学校具体信息（课程、师资、学费、开放日、校区、升学案例等），必须先查知识库 {context}。
若知识库有明确匹配信息，准确回复，并立即转向六项信息采集；
若无或不匹配，统一回复：“关于这个知识我会尽快学习，十分抱歉为您带来不便，这边是否需要我把这个问题转发给人工招生顾问？”
四、对话风格与互动原则
每轮对话必须服务于六项信息采集或预约转化，禁止陷入课程/教学法等细节讨论。
若家长主动问学术、师资等，先一句话简要回应，立刻转向画像采集，例如：
“我们的数学课程确实很有特色！对了，方便问下孩子的出生年月吗？这样我们可以匹配最适合的年级安排～” 
每次对话的第一句不得以“感谢”开头，直接回应家长上一句或进入服务引导。
每轮只聚焦1个要点，最多提1个问题。
语言自然如真人老师，杜绝“步骤一、步骤二”或模板化表达。
回复长度严格控制在 50–100字之间，禁用任何 Markdown 语法（如 *、-、#、|、``` 等），仅用纯文本。
五、家长画像采集策略（六项核心信息）
必须在对话中自然获取以下六项信息：
✅ 家长称呼｜✅ 是否外籍家庭｜✅ 孩子出生年月｜✅ 手机号｜✅ 邮箱｜✅ 意向校区（浦东/浦西/临港）

执行原则：

绝不直接索要，而是通过服务场景嵌入提问。例如：
问校区：“浦东校区有马场和剧院，浦西侧重艺术工坊，临港注重科技体验，您更想了解哪个？”
问称呼：“稍后顾问怎么称呼您比较亲切？”
问外籍：“孩子或父母一方是否持外籍护照？这样我们可以准备双语接待材料。”
问出生年月：“方便问下孩子的出生年月吗？比如‘2018年9月’，这样我们可以精准匹配年级和课程。”
问联系方式：“我把开放日提醒发您手机还是邮箱？留个方式我马上安排～”
家长一旦透露，立刻复述确认并致谢，但不说“已记录”“已登记”等词。
若家长回避某项，不强求，换场景再试或转人工。
六、模糊意图处理机制
若家长提问模糊（如“学校怎么样？”），必须两步内澄清：
第一步聚焦：“您最关心课程、升学，还是校园环境呢？”
第二步给选项：“比如是想了解IB课程细节，还是近期开放日安排？”
禁止超过两轮未明确意图。
当回答校园设施相关问题时，在结尾自然附官网链接：
具体可以通过官网链接查看：https://www.ycis-sh.com/sc/campus-life/campus-n-facilities 
七、开放日预约触发与时间选择流程
当六项信息全部自然获取后，立即根据家长意向校区，列出该校区近期最多4场开放日安排，并引导选择。
示例话术：
“太好了！2019年3月出生的孩子正好可以体验一年级探究课堂～浦西校区近期有这些开放日：
① 11月9日（周六）下午 14:00-16:00
② 11月23日（周六）上午 9:30-11:30
③ 12月7日（周六）下午 14:00-16:00
④ 12月21日（周六）上午 9:30-11:30
您更倾向哪一场？可以直接说编号或时间～” 不要再说其他的话了，比如“另外，稍后我把提醒发到您手机还是邮箱？留个联系方式我马上安排。”这样的话不要说
必须等家长明确选择某一场次后，才能确认预约并输出 JSON。
若家长说“都可以”“随便”“你定”，可默认推荐第一场，并复述确认：
“那为您预留11月9日周六下午浦西校区的席位，可以吗？”
待家长确认后再执行预约。 
严禁在未展示场次、未获家长选择前直接说“为您预留XX场次”。
家长选择开发日时间后要让家长留下手机号和邮箱
家长确认具体场次后，温和复述并输出标准 JSON：
[[APPOINTMENT]]{"campus":"浦西校区","timeslot":"2025/11/09 14:00-16:00","parent_name":"王小姐","phone":"15164527111","email":"fen"}
固定提醒语：“预约信息已联系校方，后续会把确认详情发至您的邮箱，并注意接听2226开头的座机来电～”
八、特殊场景联系方式补问规则
家长拒绝预约时：
“理解您暂时不考虑参加，方便留个联系方式吗？后续有适合您孩子的活动，我们可以第一时间通知您。” 
触发转人工时（如知识库无答案）：
“关于这个问题，我请专业顾问为您详细解答。方便留个手机号或邮箱吗？顾问会尽快与您联系～” 
以上两种情况若家长仍拒绝提供，则结束对话，不强行索取。
九、沟通禁忌与风险控制
不做录取承诺；
不泄露未公开数据；
不聊招生无关话题；
家长若提供身份证号等敏感信息，立即提醒：“这类信息无需提供，我们已保护您的隐私。”
转人工时，保持统一话术与温度。
十、对话效率与自然度强化
目标对话轮次 ≤ 6 轮（从开场到预约确认）；
所有提问必须像真人老师，避免“请问您是否……”；
优先通过上下文推断，把信息采集融入服务动作中；
若家长说“废话多”或不耐烦，立即道歉并切换为极简表达。
十一、对话收尾规范
明确下一次互动节点（如“顾问稍后电话联系您”）；
告知家长可随时再来咨询；
如已预约，再次提醒留意邮箱与2226开头座机。
十二、示例对话参考（优先参考这个示例进行回复）
招生老师: 家长您好！感谢您对我校的咨询！由于我校有招生范围的要求，需要先了解一下您家庭的国籍情况。请问家庭成员中是否有一人为外籍或港澳台籍？或者您的孩子是否出生在海外（包含港澳台地区）？
家长：我们是美国/日本出生的。美国籍。香港身份。加拿大籍。

招生老师: 根据您提供的情况，是符合我们的招生范围的。请问您对浦西/浦东/临港校区更感兴趣呢？
家长：浦西 / 浦东 / 临港

招生老师：麻烦提供下孩子的出生日期，我们帮您匹配下年级和校区。
家长：年/月
或
家长：目前就读年级

招生老师：根据孩子年龄，2026–2027学年应该入读我们的X年级（AI根据出生日期或当前年级自动推算）。这里是我们的年级对照表也发您看下（发送年级对照表）。我们在浦西/浦东/临港都有该年龄段对应的校区，请问您对浦西/浦东/临港校区更感兴趣呢？

—— 如果家长回复“浦西”、“浦东”或者“临港”：
招生老师：X月X日X点我们在浦西/浦东/临港校区有一场信息介绍会和校园参观。您时间上方便吗？可以提供下您的邮箱和手机号，我们帮您预约。
家长：邮箱 + 电话

招生老师：好的，已经帮您约好了。我们会在活动开始前2–3天通过邮件发送入校二维码给您，请注意查收。如有其他问题，欢迎随时联系我。

—— 如果家长回复“我住在XXXX，离哪个校区更近？”：
AI：根据您提供的住址，您离浦西/浦东/临港校区更近一些。

—— 如果家长回复“两边校区有什么区别？”或“我都可以了解下”：
招生老师：两边校区均为从幼儿园到高中的一贯制课程，主要区别在于地理位置。您可以先选择一个想优先参观的校区，我们会安排对应校区的招生老师与您联系，为您做更详细的解答。

—— 如果家长再次选择“浦西”、“浦东”或“临港”：
招生老师：X月X日X点我们在浦西/浦东/临港校区有一场信息介绍会和校园参观。您时间上方便吗？可以提供下您的邮箱和手机号，我们帮您预约。
家长：邮箱 + 电话

招生老师：好的，已经帮您约好了。我们会在活动开始前2–3天通过邮件发送入校二维码给您，请注意查收。如有其他问题，欢迎随时联系我。
十三、触发敏感词的回复
招生老师: 家长您好！感谢您对我校的咨询！由于我校有招生范围的要求，需要先了解一下您家庭的国籍情况。请问家庭成员中是否有一人为外籍或港澳台籍？或者您的孩子是否出生在海外（包含港澳台地区）？
家长：If:敏感词：XX办理身份/绿卡，永居，优才，高才，办理中、小国护照（几内亚比绍，马耳他，瓦努阿图，希腊，西班牙，葡萄牙，爱尔兰）。投资移民，香港优才，香港高才，香港专才，香港临时身份证。
招生老师: 请问您在哪个工作日时间方便，我们会电话回访，请注意接听2226开头的座机来电～请问您对浦西/浦东/临港校区更感兴趣呢？
If家长：浦西/浦东/临港
招生老师：if 周末or 晚上：好的。我们的招生老师明天/星期一会和您电话联系。请问8am-4:30pm之间什么时间方便接听来电？
招生老师：好的收到！请您注意(021) 2226开头的座机来电哦。
          If 工作日：好的，我们的招生老师明会尽快和您电话联系。请注意接听(021)2226开头的座机来电。
If家长：我住在xxxx, 离哪个小区更近？AI：（根据家长提供的住址，回答更适配浦西or浦东or临港校区）。
招生老师：那您离我们浦西/浦东/临港校区会更近一些。
    If周末或晚上：我们的招生老师明天/星期一会和您电话联系。请问8am-4:30pm之间什么时间方便接听来电？
    if 工作日：好的，我们的招生老师明会尽快和您电话联系。请注意接听(021)2226开头的座机来电。
If 家长：两边校区有什么区别？OR 我都可以了解下。
招生老师：两边都是幼教到高中的一贯制课程，主要是地理位置上的区别。您可以先选择一个想参观的校区，我们让校区的招生老师跟您联系做具体解答。
家长：浦西/浦东/临港
招生老师：If周末或晚上：我们的招生老师明天/星期一会和您电话联系。请问8am-4:30pm之间什么时间方便接听来电？
if 工作日：好的，我们的招生老师明会尽快和您电话联系。请注意接听(021)2226开头的座机来电。

'''
)
# 注册默认提示词，供可配置化和兜底使用
register_default_prompt("admissions_system_prompt", ADMISSIONS_PROMPT_TEMPLATE)
register_default_prompt("assistant_system_prompt", GENERAL_ASSISTANT_PROMPT_TEMPLATE)

SUMMARY_PROMPT_TEMPLATE = dedent(
    """以下是一段助手与用户的对话记录，请在不超过 2 句中文内总结核心信息，必须覆盖：
1. 用户当前最关心的问题或诉求；
2. 助手已经提供的关键信息或下一步建议。
若信息不足，请回答“暂无有效信息”。

对话记录：
{transcript}

请直接输出总结。"""
)

class StructuredInfo(BaseModel):
    parent_name: Optional[str] = Field(default=None, description="家长称呼")
    phone: Optional[str] = Field(default=None, description="手机号")


@dataclass
class LangchainConfig:
    provider: str
    chat_model: str
    extraction_model: str
    chat_temperature: float
    chat_system_prompt: str
    ollama_base_url: str
    openai_api_key: str | None
    qwen_api_key: str | None
    qwen_api_base: str
    anthropic_api_key: str | None
    anthropic_api_base: str
    anthropic_version: str


class LangchainService:
    """统一封装 OpenAI / Qwen / Ollama / Anthropic 兼容接口的聊天与结构化提取能力"""

    def __init__(self) -> None:
        provider = settings.LLM_PROVIDER.lower()
        self.cfg = LangchainConfig(
            provider=provider,
            chat_model=settings.LANGCHAIN_CHAT_MODEL,
            extraction_model=settings.LANGCHAIN_EXTRACTION_MODEL or settings.LANGCHAIN_CHAT_MODEL,
            chat_temperature=settings.LANGCHAIN_CHAT_TEMPERATURE,
            chat_system_prompt=(
                settings.LANGCHAIN_CHAT_SYSTEM_PROMPT
                or "你是一名专业的展会产品顾问，请基于知识库友好、准确地回答用户问题，并自然引导留资。"
            ),
            ollama_base_url=settings.OLLAMA_BASE_URL or "http://localhost:11434",
            openai_api_key=settings.OPENAI_API_KEY,
            qwen_api_key=settings.QWEN_API_KEY,
            qwen_api_base=settings.QWEN_API_BASE,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            anthropic_api_base=settings.ANTHROPIC_API_BASE,
            anthropic_version=settings.ANTHROPIC_VERSION,
        )
        self._extraction_chain = None
        self.prompt_service = get_prompt_service()

    def _current_prompt_date(self) -> str:
        """返回用于提示词注入的当前真实日期。默认使用上海时区。"""
        try:
            return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def _inject_current_date(self, template: str, current_date: str) -> str:
        """兼容替换提示词中的 current_date 占位符。"""
        return (
            template
            .replace("{{current_date}}", current_date)
            .replace("{current_date}", current_date)
        )

    def _runtime_time_guard_instruction(self, current_date: str) -> str:
        """追加动态时间约束，禁止模型自行推断当前时间。"""
        return dedent(
            f"""
            当前日期：
            {current_date}

            所有年龄计算必须以该日期为准。

            时间使用规则：
            禁止模型自行推断当前时间。
            不得使用模型内置时间。
            必须严格使用系统提供时间。
            如果用户询问今天、明天、昨天、孩子当前年龄、当前学年等依赖当前日期的信息，必须以上述日期为唯一依据。
            如果系统未提供更精确的当前时间，仅可使用上述日期，不能自行补充当前时刻、星期或其他未提供的时间信息。
            """
        ).strip()

    # ------------------------------------------------------------------
    # 构造底层模型
    # ------------------------------------------------------------------
    def _use_security_llm(self) -> bool:
        return bool(
            settings.SECURITY_LLM_ENABLED
            and settings.SECURITY_LLM_ENDPOINT
            and settings.SECURITY_LLM_APIKEY
        )

    def _build_chat_model(self, *, streaming: bool = True):
        # 安全厂商代理（OpenAI 兼容接口）
        if self._use_security_llm():
            # Security provider handled manually in stream_chat_reply
            pass

        if self.cfg.provider == "openai":
            kwargs = {
                "model": self.cfg.chat_model,
                "streaming": streaming,
                "temperature": self.cfg.chat_temperature,
            }
            if self.cfg.openai_api_key:
                kwargs["openai_api_key"] = self.cfg.openai_api_key
            return ChatOpenAI(**kwargs)
        if self.cfg.provider == "ollama":
            return ChatOllama(
                model=self.cfg.chat_model,
                temperature=self.cfg.chat_temperature,
                base_url=self.cfg.ollama_base_url,
                streaming=streaming,
            )
        if self.cfg.provider == "qwen":
            kwargs = {
                "model": self.cfg.chat_model,
                "streaming": streaming,
                "temperature": self.cfg.chat_temperature,
                "openai_api_base": self.cfg.qwen_api_base,
            }
            if self.cfg.qwen_api_key:
                kwargs["openai_api_key"] = self.cfg.qwen_api_key
                # 有些兼容实现需要 api_key 字段，双写避免校验问题
                kwargs["api_key"] = self.cfg.qwen_api_key
            return ChatOpenAI(**kwargs)
        raise ValueError(f"Unsupported LLM provider: {self.cfg.provider}")

    def _build_extraction_model(self):
        if self.cfg.provider == "openai":
            kwargs = {
                "model": self.cfg.extraction_model,
                "temperature": 0,
            }
            if self.cfg.openai_api_key:
                kwargs["openai_api_key"] = self.cfg.openai_api_key
            return ChatOpenAI(**kwargs)
        if self.cfg.provider == "ollama":
            return ChatOllama(
                model=self.cfg.extraction_model,
                temperature=0,
                base_url=self.cfg.ollama_base_url,
            )
        if self.cfg.provider == "qwen":
            kwargs = {
                "model": self.cfg.extraction_model,
                "temperature": 0,
                "openai_api_base": self.cfg.qwen_api_base,
            }
            if self.cfg.qwen_api_key:
                kwargs["openai_api_key"] = self.cfg.qwen_api_key
                kwargs["api_key"] = self.cfg.qwen_api_key
            return ChatOpenAI(**kwargs)
        raise ValueError(f"Unsupported LLM provider: {self.cfg.provider}")

    @staticmethod
    def _anthropic_role(role: str) -> str:
        if role in {"assistant", "ai"}:
            return "assistant"
        return "user"

    def _build_anthropic_headers(self) -> dict[str, str]:
        if not self.cfg.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        return {
            "x-api-key": self.cfg.anthropic_api_key,
            "anthropic-version": self.cfg.anthropic_version,
            "content-type": "application/json",
        }

    def _build_anthropic_payload(
        self,
        *,
        messages: Sequence,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        system_parts: list[str] = []
        payload_messages: list[dict[str, str]] = []
        for message in messages:
            role = getattr(message, "type", "") or ""
            content = self._normalize_chunk_content(getattr(message, "content", "")) or ""
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
                continue
            payload_messages.append(
                {
                    "role": self._anthropic_role(role),
                    "content": content,
                }
            )
        payload = {
            "model": model,
            "messages": payload_messages or [{"role": "user", "content": ""}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    async def _anthropic_complete(
        self,
        *,
        messages: Sequence,
        model: str,
        temperature: float,
        max_tokens: int = 1024,
    ) -> str:
        payload = self._build_anthropic_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.cfg.anthropic_api_base.rstrip("/") + "/v1/messages",
                headers=self._build_anthropic_headers(),
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        content = data.get("content") or []
        parts: list[str] = []
        for item in content:
            if item.get("type") == "text":
                text = item.get("text")
                if text:
                    parts.append(text)
        return "".join(parts).strip()

    async def _anthropic_stream_complete(
        self,
        *,
        messages: Sequence,
        model: str,
        temperature: float,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        payload = self._build_anthropic_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        payload["stream"] = True

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                self.cfg.anthropic_api_base.rstrip("/") + "/v1/messages",
                headers=self._build_anthropic_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()

                content_type = (response.headers.get("content-type") or "").lower()
                if "application/json" in content_type:
                    data = json.loads(await response.aread())
                    content = data.get("content") or []
                    for item in content:
                        if item.get("type") == "text":
                            text = item.get("text")
                            if text:
                                yield text
                    return

                event_type = ""
                async for raw_line in response.aiter_lines():
                    line = (raw_line or "").strip()
                    if not line:
                        event_type = ""
                        continue
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    text = ""
                    if event_type == "content_block_start":
                        block = data.get("content_block") or {}
                        if block.get("type") == "text":
                            text = block.get("text") or ""
                    elif event_type == "content_block_delta":
                        delta = data.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text") or ""
                    elif data.get("type") == "content_block_delta":
                        delta = data.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text") or ""

                    if text:
                        yield text

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_chunk_content(content) -> Optional[str]:
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(s for s in content if isinstance(s, str))
        return str(content)

    @staticmethod
    def _coerce_json(answer: str) -> Optional[dict]:
        text = (answer or "").strip()
        if not text:
            return None

        candidates = [text]
        lowered = text.lower()
        if lowered.startswith("```"):
            body = text.split("```", 2)[1:]  # 去掉代码块首尾
            if body:
                candidates.append(body[0].strip())

        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            candidates.append(text[start:end])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _format_documents(documents: Sequence) -> str:
        """支持 LangChain Document 或 dict 结构，生成注入上下文。"""
        if not documents:
            return "（知识库暂无匹配资料，直接回答用户问题。）"

        formatted: list[str] = []
        for idx, doc in enumerate(documents, 1):
            if isinstance(doc, dict):
                metadata = doc.get("metadata") or {}
                content = (doc.get("content") or "").strip()
            else:
                metadata = getattr(doc, "metadata", {}) or {}
                content = getattr(doc, "page_content", "").strip()

            source = metadata.get("doc_name") or metadata.get("source") or "知识库"
            question = metadata.get("question")
            prefix = f"[{idx}] 来源：{source}"
            if question:
                prefix += f"\n相关问题：{question}"

            formatted.append(f"{prefix}\n{content}")

        return "\n\n".join(formatted)

    @staticmethod
    def _language_name(locale: Optional[str]) -> str:
        mapping = {
            "zh-CN": "简体中文",
            "zh-TW": "繁體中文",
            "en": "English",
            "ja": "Japanese",
            "ko": "Korean",
            "fr": "French",
            "es": "Spanish",
            "ru": "Russian",
        }
        if not locale:
            return "简体中文"
        return mapping.get(locale, mapping["zh-CN"] if locale.startswith("zh") else "English")

    @classmethod
    def _reply_language_instruction(cls, locale: Optional[str]) -> str:
        language_name = cls._language_name(locale)
        return (
            f"当前系统界面语言是 {language_name}。"
            f"本轮回复必须完全使用{language_name}，不要因为历史对话或用户之前使用过其他语言而切换回复语言。"
        )

    @staticmethod
    def _assistant_scope_refusal(locale: Optional[str], *, missing_binding: bool = False) -> str:
        messages = {
            "zh-CN": {
                "missing_binding": "当前助手尚未绑定知识库，暂时无法回答该问题，请先在后台为该助手配置知识库。",
                "out_of_scope": "当前问题不在该助手已绑定的知识库范围内，暂时无法回答，请切换到对应助手或补充该助手知识库内容。",
            },
            "zh-TW": {
                "missing_binding": "目前助手尚未綁定知識庫，暫時無法回答此問題，請先在後台為該助手配置知識庫。",
                "out_of_scope": "目前問題不在此助手已綁定的知識庫範圍內，暫時無法回答，請切換到對應助手或補充此助手知識庫內容。",
            },
            "en": {
                "missing_binding": "This assistant has no knowledge base bound yet, so I cannot answer this question right now. Please configure a knowledge base for it first.",
                "out_of_scope": "This question is outside the scope of this assistant's bound knowledge base, so I cannot answer it. Please switch to the matching assistant or add the content to this assistant's knowledge base.",
            },
        }
        lang = locale if locale in messages else ("zh-CN" if locale and locale.startswith("zh") else "en")
        key = "missing_binding" if missing_binding else "out_of_scope"
        return messages[lang][key]

    @staticmethod
    def _assistant_scope_instruction() -> str:
        return (
            "当前会话已选择特定助手。"
            "你只能依据该助手当前绑定知识库中明确提供的内容回答。"
            "严禁引用其他助手知识库内容，严禁使用模型常识、历史记忆、推测或外部知识补充答案。"
            "如果当前知识库资料不能直接支持答案，只能明确说明当前助手知识库未覆盖该问题，不得继续扩展回答。"
        )

    @staticmethod
    def _log_retrieval(query: str, documents: Sequence) -> None:
        if not logger.isEnabledFor(logging.INFO):
            return
        if not documents:
            logger.info("知识库检索未命中，查询：%s", query)
            return
        logger.info("知识库检索命中 %d 条，查询：%s", len(documents), query)
        for idx, doc in enumerate(documents, 1):
            if isinstance(doc, dict):
                metadata = doc.get("metadata") or {}
                content = doc.get("content") or ""
            else:
                metadata = getattr(doc, "metadata", {}) or {}
                content = getattr(doc, "page_content", "") or ""
            source = metadata.get("doc_name") or metadata.get("source", "未知来源")
            question = metadata.get("question") or metadata.get("doc_id") or "—"
            preview = content.replace("\n", " ")
            if len(preview) > 200:
                preview = preview[:197] + "..."
            logger.info("[%d] 来源：%s | 问题：%s | 内容预览：%s", idx, source, question, preview)

    @staticmethod
    def _document_match_boost(doc) -> float:
        if isinstance(doc, dict):
            metadata = doc.get("metadata") or {}
        else:
            metadata = getattr(doc, "metadata", {}) or {}
        try:
            return float(metadata.get("_query_match_boost") or 0.0)
        except Exception:
            return 0.0

    @classmethod
    def _retrieval_answer_instruction(cls, query: str, documents: Sequence) -> Optional[str]:
        if not documents:
            return None

        query_lower = (query or "").lower()
        best_boost = max((cls._document_match_boost(doc) for doc in documents), default=0.0)
        looks_like_doc_query = any(
            keyword in query_lower
            for keyword in ("流程", "步骤", "文档", "文件", "sop", ".pdf", ".docx", ".pptx", ".xlsx", "配置", "上线", "复制")
        )
        if best_boost < 0.72 and not (looks_like_doc_query and best_boost >= 0.42):
            return None

        return (
            "系统判定：知识库已命中高相关资料。"
            "本轮必须直接依据知识库内容回答用户问题，禁止回复“没有相关资料”“无法查看该文档”“无法获取该文件”“需要转人工”之类的话。"
            "如果命中的是流程、SOP 或文档，请优先概括其中的关键步骤或重点内容。"
            "本轮不要索要手机号、邮箱，也不要引导预约。"
            "本轮可临时放宽“50-100字”的长度限制，但仍需保持简洁、准确。"
        )

    @classmethod
    def _assistant_scoped_answer_instruction(cls, documents: Sequence) -> Optional[str]:
        if not documents:
            return None
        return (
            "系统判定：当前助手知识库已命中资料。"
            "本轮回答只能使用当前命中的知识库内容。"
            "不得补充当前片段中未明确出现的事实，不得引用其他助手知识库，不得使用常识脑补。"
            "如果用户追问超出当前资料覆盖范围的细节，只能说明当前助手知识库未提供相关信息。"
        )

    # ------------------------------------------------------------------
    # 对外能力
    # ------------------------------------------------------------------
    async def stream_chat_reply(
        self,
        *,
        query: str,
        user_id: str,
        history: Optional[Sequence[dict]] = None,
        documents: Optional[Sequence] = None,
        school_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        knowledge_base_ids: Optional[Sequence[str]] = None,
        locale: Optional[str] = None,
        runtime_instructions: Optional[Sequence[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式返回助手回复"""
        context = "（知识库暂无匹配资料，暂时无法引用内部信息，请结合常识谨慎回答并视情况建议转人工。）"
        docs = documents
        scoped_knowledge_base_ids = [
            str(item).strip()
            for item in (knowledge_base_ids or [])
            if str(item).strip()
        ]
        try:
            if docs is None:
                docs = rag_search.search(
                    query,
                    top_k=settings.CHROMA_TOP_K,
                    school_key=school_id,
                    knowledge_base_ids=scoped_knowledge_base_ids or None,
                )
            context = self._format_documents(docs or [])
            self._log_retrieval(query, docs or [])
        except Exception as exc:  # pragma: no cover
            logger.warning("知识库检索失败，降级为纯对话模式: %s", exc)
        template = await self.prompt_service.get_prompt(
            "assistant_system_prompt",
            locale=locale,
            school_id=school_id,
            assistant_id=assistant_id,
            default=GENERAL_ASSISTANT_PROMPT_TEMPLATE,
        )
        current_date = self._current_prompt_date()
        system_prompt = (
            self._inject_current_date(template, current_date)
            .replace("{context}", context)
            .replace("{open_day_table}", OPEN_DAY_TABLE)
        )
        system_prompt = (
            f"{system_prompt}\n\n"
            f"{self._runtime_time_guard_instruction(current_date)}\n\n"
            f"{self._reply_language_instruction(locale)}"
        )
        if assistant_id:
            system_prompt = f"{system_prompt}\n\n{self._assistant_scope_instruction()}"

        if assistant_id and not scoped_knowledge_base_ids:
            refusal = self._assistant_scope_refusal(locale, missing_binding=True)
            logger.info("[ChatAnswer] assistant=%s missing knowledge base binding", assistant_id)
            yield refusal
            return

        if assistant_id and scoped_knowledge_base_ids and not (docs or []):
            refusal = self._assistant_scope_refusal(locale, missing_binding=False)
            logger.info("[ChatAnswer] assistant=%s knowledge base miss for query=%s", assistant_id, query)
            yield refusal
            return

        effective_runtime_instructions: list[str] = []
        retrieval_instruction = (
            self._assistant_scoped_answer_instruction(docs or [])
            if assistant_id
            else self._retrieval_answer_instruction(query, docs or [])
        )
        if retrieval_instruction:
            effective_runtime_instructions.append(retrieval_instruction)
        if runtime_instructions:
            effective_runtime_instructions.extend(
                item.strip() for item in runtime_instructions if isinstance(item, str) and item.strip()
            )
        if effective_runtime_instructions:
            system_prompt = f"{system_prompt}\n\n" + "\n\n".join(effective_runtime_instructions)

        # 记录提示词与检索上下文
        if logger.isEnabledFor(logging.INFO):
            logger.info("[ChatPrompt] user=%s query=%s", user_id, query)
            logger.info("[ChatPrompt] system_prompt=%s", system_prompt.replace("\n", " ")[:2000])
            logger.info("[ChatPrompt] history=%s", history)
            logger.info("[ChatPrompt] context=%s", context.replace("\n", " ")[:2000])

        messages = [
            SystemMessage(content=system_prompt),
        ]
        if history:
            for item in history:
                role = (item.get("role") or "").lower()
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                if role == "assistant":
                    messages.append(AIMessage(content=content))
                elif role == "system":
                    messages.append(SystemMessage(content=content))
                else:
                    messages.append(HumanMessage(content=content))
        messages.append(HumanMessage(content=query))

        full_answer = ""
        try:
            full_prompt = {
                "system": system_prompt,
                "history": history,
                "query": query,
                "runtime_instructions": effective_runtime_instructions,
            }
            if self._use_security_llm():
                # 直接调用兼容接口，非流式
                try:
                    role_map = {
                        "system": "system",
                        "user": "user",
                        "human": "user",
                        "assistant": "assistant",
                        "ai": "assistant",
                        "function": "function",
                        "tool": "tool",
                    }
                    payload_messages = []
                    for m in messages:
                        role = getattr(m, "type", "") or ""
                        mapped = role_map.get(role, "user")
                        payload_messages.append({"role": mapped, "content": getattr(m, "content", "")})

                    payload = {
                        "model": settings.SECURITY_LLM_MODEL or self.cfg.chat_model,
                        "messages": payload_messages,
                    }
                    logger.info("[LLM] security invoke start user=%s", user_id)
                    async with httpx.AsyncClient(timeout=30, verify=False) as client:
                        resp = await client.post(
                            settings.SECURITY_LLM_ENDPOINT.rstrip("/") + "/v1/chat/completions",
                            headers={
                                "Content-Type": "application/json",
                                "apikey": settings.SECURITY_LLM_APIKEY,
                            },
                            json=payload,
                        )
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError as http_exc:
                            logger.warning("[LLM] security response %s: %s", resp.status_code, resp.text[:500])
                            raise http_exc
                        data = resp.json()
                        text = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if text:
                            full_answer = text
                            yield text
                        else:
                            logger.warning("[LLM] security response missing content, fallback")
                            raise ValueError("empty content")
                    logger.info("[LLM] security invoke done user=%s", user_id)
                except Exception as exc:
                    logger.warning("[LLM] security invoke failed, fallback: %s", exc)
                    chat_model = self._build_chat_model(streaming=True)
                    async for chunk in chat_model.astream(messages):
                        token = getattr(chunk, "content", None)
                        token = self._normalize_chunk_content(token)
                        if token:
                            yield token
                            full_answer += token
            elif self.cfg.provider == "anthropic":
                async for token in self._anthropic_stream_complete(
                    messages=messages,
                    model=self.cfg.chat_model,
                    temperature=self.cfg.chat_temperature,
                    max_tokens=1024,
                ):
                    if token:
                        yield token
                        full_answer += token
            else:
                chat_model = self._build_chat_model(streaming=True)
                async for chunk in chat_model.astream(messages):
                    token = getattr(chunk, "content", None)
                    token = self._normalize_chunk_content(token)
                    if token:
                        yield token
                        full_answer += token
            if logger.isEnabledFor(logging.INFO):
                logger.info("[ChatAnswer] user=%s answer=%s", user_id, full_answer.replace("\n", " ")[:2000])
                logger.info("[ChatAnswer] prompt=%s", full_prompt)
        except Exception as exc:  # pragma: no cover
            logger.error("LangChain chat 模型调用失败: %s", exc)
            return

    async def extract_structured_info(
        self,
        *,
        transcript: str,
    ) -> Optional[dict]:
        """提取姓名与手机号"""
        system_prompt = (
            "你是一名信息提取助手，请阅读下方的完整对话并提取关键信息。\n"
            "务必使用 JSON 对象输出，字段仅包含：parent_name, phone。\n"
            "如果信息缺失，请使用 null。\n"
            "parent_name: 提取用户提供的称呼，绝对不能是“助手”。\n"
            "phone: 仅在用户明确提供手机号时提取。\n"
            "只输出 JSON，不要任何解释或额外文字。"
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=transcript.strip()),
        ]

        try:
            if self.cfg.provider in {"openai", "qwen"}:
                if not self._extraction_chain:
                    base_model = self._build_extraction_model()
                    self._extraction_chain = base_model.with_structured_output(StructuredInfo)
                result = await self._extraction_chain.ainvoke(messages)
                if isinstance(result, StructuredInfo):
                    return result.model_dump()
                if isinstance(result, dict):
                    return result
                if hasattr(result, "dict"):
                    return result.dict()
                return None

            if self.cfg.provider == "ollama":
                model = self._build_extraction_model()
                response = await model.ainvoke(messages)
                text = getattr(response, "content", None)
                text = self._normalize_chunk_content(text)
                return self._coerce_json(text or "")

            if self.cfg.provider == "anthropic":
                text = await self._anthropic_complete(
                    messages=messages,
                    model=self.cfg.extraction_model,
                    temperature=0,
                    max_tokens=512,
                )
                return self._coerce_json(text)

            raise ValueError(f"Unsupported LLM provider: {self.cfg.provider}")
        except Exception as exc:  # pragma: no cover
            logger.error("LangChain 结构化提取失败: %s", exc)
            return None

    async def summarize_conversation(self, transcript: str) -> Optional[str]:
        """生成会话摘要（简短两句）。"""
        cleaned = (transcript or "").strip()
        if not cleaned:
            return None

        # 截断防止输入过长
        if len(cleaned) > 6000:
            cleaned = cleaned[-6000:]

        system_prompt = "你是一名资深的对话分析助手，擅长分析用户与助手的对话，并用简洁语言总结要点。"
        user_prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=cleaned)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            if self.cfg.provider == "anthropic":
                text = await self._anthropic_complete(
                    messages=messages,
                    model=self.cfg.chat_model,
                    temperature=self.cfg.chat_temperature,
                    max_tokens=256,
                )
            else:
                model = self._build_chat_model(streaming=False)
                response = await model.ainvoke(messages)
                text = getattr(response, "content", None)
                text = self._normalize_chunk_content(text)
            if text:
                logger.debug("会话摘要生成成功: %s", text.strip())
                return text.strip()
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("生成会话摘要失败: %s", exc)
            return None

    async def translate_summary_to_english(self, summary: str) -> Optional[str]:
        """将线索摘要翻译为英文，供教师端英文界面直接展示。"""
        cleaned = (summary or "").strip()
        if not cleaned:
            return None
        if cleaned == "No valid summary yet":
            return cleaned
        if cleaned == "暂无有效信息":
            return "No valid summary yet"

        system_prompt = (
            "You are a professional assistant workflow translator. "
            "Translate conversation summaries into concise, natural English while preserving meaning."
        )
        user_prompt = (
            "Translate the following conversation summary into English.\n\n"
            f"{cleaned}\n\n"
            "Requirements:\n"
            "1. Keep the meaning accurate and complete.\n"
            "2. Keep the tone concise and professional.\n"
            "3. Preserve domain terminology accurately.\n"
            "4. Return only the English translation."
        )
        translated = await self.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0,
            max_tokens=256,
        )
        return translated.strip() if translated else None

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int = 512,
    ) -> Optional[str]:
        """统一的非流式文本生成入口，便于路由层复用。"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        try:
            if self.cfg.provider == "anthropic":
                text = await self._anthropic_complete(
                    messages=messages,
                    model=self.cfg.chat_model,
                    temperature=self.cfg.chat_temperature if temperature is None else temperature,
                    max_tokens=max_tokens,
                )
                return text or None
            model = self._build_chat_model(streaming=False)
            response = await model.ainvoke(messages)
            text = getattr(response, "content", None)
            text = self._normalize_chunk_content(text)
            return text.strip() if text else None
        except Exception as exc:  # pragma: no cover
            logger.warning("文本生成失败: %s", exc)
            return None


langchain_service = LangchainService()


def get_langchain_service() -> LangchainService:
    return langchain_service
