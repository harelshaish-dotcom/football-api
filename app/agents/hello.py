"""First LangChain + OpenAI sanity check. Run with:  python -m app.agents.hello"""

from app.agents.llm import get_llm

llm = get_llm()

if __name__ == "__main__":
    response = llm.invoke("Say hello in one short sentence.")
    print(response.content)
