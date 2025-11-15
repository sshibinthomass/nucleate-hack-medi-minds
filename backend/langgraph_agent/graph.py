from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, add_messages, START
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from typing import List, Annotated
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain.tools import BaseTool
import os
from langgraph_agent.prompts import get_scout_system_prompt


class AgentState(BaseModel):
    messages: Annotated[List, add_messages]


def build_agent_graph(tools: List[BaseTool] = []):
    llm = ChatOpenAI(name="Scout", model="gpt-4.1-mini")
    if tools:
        llm = llm.bind_tools(tools)
        system_prompt = get_scout_system_prompt(
            working_dir=os.environ.get("MCP_FILESYSTEM_DIR", ""),
        )
    else:
        system_prompt = get_scout_system_prompt()

    def assistant(state: AgentState) -> AgentState:
        response = llm.invoke([SystemMessage(content=system_prompt)] + state.messages)
        state.messages.append(response)
        return state

    builder = StateGraph(AgentState)

    builder.add_node("Scout", assistant)
    builder.add_node(ToolNode(tools))

    builder.add_edge(START, "Scout")
    builder.add_conditional_edges(
        "Scout",
        tools_condition,
    )
    builder.add_edge("tools", "Scout")

    return builder.compile(checkpointer=MemorySaver())


# visualize graph
if __name__ == "__main__":
    from IPython.display import display, Image

    graph = build_agent_graph()
    display(Image(graph.get_graph().draw_mermaid_png()))
