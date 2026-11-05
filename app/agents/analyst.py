"""Match analyst agent: answers questions about a team's season or recent
form, using the tools in app.agents.tools. Run with:
    python -m app.agents.analyst "How is Arsenal doing this season?"
"""

import sys

from langchain_core.messages import HumanMessage, ToolMessage

from app.agents.llm import get_llm
from app.agents.tools import get_recent_form, get_season_record

TOOLS = [get_season_record, get_recent_form]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

llm_with_tools = get_llm().bind_tools(TOOLS)


def ask(question: str) -> str:
    messages = [HumanMessage(question)]
    response = llm_with_tools.invoke(messages)
    messages.append(response)

    while response.tool_calls:
        for call in response.tool_calls:
            result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        response = llm_with_tools.invoke(messages)
        messages.append(response)

    return response.content


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "How is Arsenal doing this season?"
    print(ask(question))
