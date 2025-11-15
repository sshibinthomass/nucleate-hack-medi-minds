import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
from langchain.tools import BaseTool
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import AIMessage

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.states.chatbotState import ChatbotState
from langgraph_agent.prompts import get_doctor_system_prompt
from langgraph_agent.mcps.config import mcp_config

load_dotenv()


class DoctorChatbotNode:
    """
    Doctor Chatbot node implementation with tool support.
    This node is specifically designed for doctor use cases and only loads
    patient specialist tools and Gmail tools.
    Handles tool calls by executing them and returning results.
    """

    def __init__(self, model, tools: Optional[List[BaseTool]] = None):
        """
        Initialize the doctor chatbot node with an LLM and optional tools.

        Args:
            model: The language model to use
            tools: Optional list of tools to bind to the LLM (patient tools and Gmail only)
        """
        self.llm = model
        self.tools = tools or []
        from langgraph.prebuilt import ToolNode

        self.tool_node = ToolNode(self.tools) if self.tools else None

        # Bind tools to LLM if provided
        if self.tools:
            self.llm = self.llm.bind_tools(self.tools)

    async def process(self, state: ChatbotState) -> dict:
        """
        Processes the input state and generates a chatbot response.
        Returns the AI response as an AIMessage object to maintain conversation history.
        If tools are available, includes system prompt.
        Handles tool calls by executing them and getting the final response.
        Supports multiple rounds of tool calls if needed.
        """
        # Create a copy of messages to avoid modifying the input state
        print("Inside Doctor Chatbot Node")
        messages = list(state["messages"])

        # Add system prompt if tools are available and not already present
        if self.tools:
            # Use the Doctor Assistant system prompt when tools are available
            system_prompt = get_doctor_system_prompt(
                working_dir=os.environ.get("MCP_FILESYSTEM_DIR", ""),
            )
            # Prepend system message if not already present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=system_prompt)] + messages

        # Handle tool calls in a loop (in case multiple rounds are needed)
        max_tool_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            # Get response from LLM
            response = self.llm.invoke(messages)
            print("Response from LLM:", response)
            # Ensure response is an AIMessage
            if not isinstance(response, AIMessage):
                if hasattr(response, "content") and hasattr(response, "type"):
                    response = AIMessage(content=response.content)
                elif isinstance(response, dict) and "content" in response:
                    response = AIMessage(content=response["content"])
                elif isinstance(response, str):
                    response = AIMessage(content=response)
                else:
                    response = AIMessage(content=str(response))

            # Check if response has tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Display tool call information
                print("\n\n< TOOL CALLS DETECTED >\n")

                for tool_call in response.tool_calls:
                    # Handle both dict and object-style tool calls
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "unknown")
                        tool_args = tool_call.get("args", {})
                        tool_id = tool_call.get("id", "")
                    else:
                        # Handle ToolCall objects with attributes (LangChain format)
                        tool_name = getattr(tool_call, "name", "unknown")
                        tool_id = getattr(tool_call, "id", "")

                        # Get args - could be attribute, method, or in __dict__
                        tool_args = {}
                        if hasattr(tool_call, "args"):
                            args_val = tool_call.args
                            # args might be a dict, string, or other type
                            if isinstance(args_val, dict):
                                tool_args = args_val
                            elif isinstance(args_val, str):
                                try:
                                    import json

                                    tool_args = json.loads(args_val)
                                except (json.JSONDecodeError, ValueError):
                                    tool_args = {"raw": args_val}
                            elif args_val is not None:
                                tool_args = args_val

                        # Also try to get from __dict__ if available
                        if not tool_args and hasattr(tool_call, "__dict__"):
                            tool_args = tool_call.__dict__.get("args", {})

                    print(f"< TOOL CALL: {tool_name} >")
                    if tool_id:
                        print(f"Tool ID: {tool_id}")
                    if tool_args and isinstance(tool_args, dict) and len(tool_args) > 0:
                        print(f"Arguments: {tool_args}")
                    elif tool_args and not isinstance(tool_args, dict):
                        print(f"Arguments: {tool_args}")
                    else:
                        print("Arguments: (no arguments required)")
                    print()

                # Add the AI response with tool calls to messages
                messages.append(response)
                print("Messages after tool call response:", messages)
                # Execute tools using ToolNode
                if self.tool_node:
                    tool_state = {"messages": messages}
                    tool_result = await self.tool_node.ainvoke(tool_state)
                    tool_messages = tool_result.get("messages", [])
                    messages.extend(tool_messages)

                # Continue loop to get final response after tool execution
                continue

            # No tool calls, return the response
            return {"messages": [response]}

        # If we've exceeded max iterations, return the last response
        return {"messages": [response]}


async def load_doctor_chatbot_tools():
    """
    Load MCP tools for doctor chatbot. This function sets up MCP client,
    gets tools from patient_specialist and gmail MCP servers only.
    Returns the list of tools.
    """
    # Create a filtered config with only patient_specialist and gmail servers
    filtered_config = {
        "mcpServers": {
            "patient_specialist": mcp_config["mcpServers"].get("patient_specialist"),
            "gmail": mcp_config["mcpServers"].get("gmail"),
        }
    }

    # Remove None values (servers that don't exist)
    filtered_config["mcpServers"] = {
        k: v for k, v in filtered_config["mcpServers"].items() if v is not None
    }

    # Set up MCP client and get tools
    client = MultiServerMCPClient(connections=filtered_config["mcpServers"])
    # the get_tools() method returns a list of tools from all the connected servers
    tools = await client.get_tools()

    return tools


if __name__ == "__main__":
    import asyncio
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langchain_core.messages import HumanMessage, SystemMessage

    async def main():
        """
        Initialize the Doctor Chatbot node and run the agent conversation loop.
        """
        # Create LLM instance
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4.1-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()

        # Load doctor chatbot tools (patient and gmail only)
        tools = await load_doctor_chatbot_tools()
        print(f"Doctor chatbot tools loaded: {len(tools)}")

        # Create DoctorChatbotNode instance with tools
        node = DoctorChatbotNode(llm, tools=tools)

        # Default example
        user_input = "Search for patients with diabetes"
        print("\n ----  USER  ---- \n\n", user_input)
        print("\n ----  ASSISTANT  ---- \n\n")

        # Create state with user message
        state = {
            "messages": [
                SystemMessage(
                    content="You are Medi-Mind, a medical assistant for doctors. You help doctors manage patient information, search patient records, and send emails. Always be professional and maintain patient confidentiality."
                ),
                HumanMessage(content=user_input),
            ]
        }

        # Process with the node (now async)
        result = await node.process(state)

        # Extract and display the response
        result_messages = result.get("messages", [])
        if result_messages:
            last_message = result_messages[-1]
            # Extract content if it's a message object
            if hasattr(last_message, "content"):
                response_text = last_message.content
            elif isinstance(last_message, dict) and "content" in last_message:
                response_text = last_message["content"]
            else:
                response_text = str(last_message)

            # Print the response
            print(response_text)
        else:
            print("No response generated")

    # Run the async main function
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())

