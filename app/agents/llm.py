"""Shared LLM factory, so agent code doesn't repeat model setup."""

from langchain_openai import ChatOpenAI

from app.core.config import AGENT_MODEL


def get_llm(**kwargs) -> ChatOpenAI:
    return ChatOpenAI(model=AGENT_MODEL, **kwargs)
