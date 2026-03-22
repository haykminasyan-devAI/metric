import logging
import os
from dotenv import load_dotenv

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
    function_tool,
)
from livekit.agents.voice.room_io import RoomOptions
from livekit.plugins import openai, silero

from rag import BankRetriever
from prompts import build_system_prompt

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

retriever = BankRetriever()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_DEFAULT_MODEL = "qwen/qwen3-next-80b-a3b-instruct"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def _build_llm():
    if LLM_PROVIDER == "openai":
        model = LLM_MODEL or OPENAI_DEFAULT_MODEL
        logger.info(f"LLM: OpenAI {model}")
        return openai.LLM(model=model)

    model = LLM_MODEL or NVIDIA_DEFAULT_MODEL
    logger.info(f"LLM: NVIDIA {model}")
    return openai.LLM(
        model=model,
        base_url=NVIDIA_BASE_URL,
        api_key=os.getenv("NVIDIA_API_KEY"),
    )


class BankAgent(Agent):
    def __init__(self):
        super().__init__(instructions=build_system_prompt())

    @function_tool
    async def search_bank_data(self, query: str) -> str:
        """Search the bank knowledge base for information about loans, deposits, or branches.
        Call this tool whenever the user asks about any banking product or branch location.

        Args:
            query: The user's question or topic to search for in Armenian or English.
        """
        logger.info(f"RAG search: {query}")
        result = retriever.retrieve(query, k=5)
        logger.info(f"RAG returned {len(result)} chars")
        return result


async def entrypoint(ctx: JobContext):
    logger.info("Agent starting...")

    if not retriever.is_index_built():
        logger.error("RAG index not found! Run: python agent/build_index.py")
        return

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(language="hy"),
        llm=_build_llm(),
        tts=openai.TTS(voice="alloy"),
    )

    await session.start(
        agent=BankAgent(),
        room=ctx.room,
        room_options=RoomOptions(participant_identity=participant.identity),
    )

    await session.say(
        "\u0532\u0561\u0580\u0587 \u0541\u0565\u0566\u0589 \u0535\u057d \u0570\u0561\u0575\u056f\u0561\u056f\u0561\u0576 \u0562\u0561\u0576\u056f\u0565\u0580\u056b \u0570\u0561\u0573\u0561\u056d\u0578\u0580\u0564\u0576\u0565\u0580\u056b \u057d\u057a\u0561\u057d\u0561\u0580\u056f\u0574\u0561\u0576 \u0585\u0563\u0576\u0561\u056f\u0561\u0576\u0576 \u0565\u0574\u0589 "
        "\u053f\u0561\u0580\u0578\u0572 \u0565\u0574 \u0585\u0563\u0576\u0565\u056c \u057e\u0561\u0580\u056f\u0565\u0580\u056b, \u0561\u057e\u0561\u0576\u0564\u0576\u0565\u0580\u056b \u0587 \u0574\u0561\u057d\u0576\u0561\u0573\u0575\u0578\u0582\u0572\u0576\u0565\u0580\u056b \u057e\u0565\u0580\u0561\u0562\u0565\u0580\u0575\u0561\u056c \u0570\u0561\u0580\u0581\u0565\u0580\u056b\u0576\u0589 "
        "\u053b\u0552\u0576\u0579\u0578\u057e \u056f\u0561\u0580\u0578\u0572 \u0565\u0574 \u0585\u0563\u0576\u0565\u056c\u0589",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
