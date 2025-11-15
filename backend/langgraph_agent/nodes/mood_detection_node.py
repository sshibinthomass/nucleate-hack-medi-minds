import os
import sys
from pathlib import Path
from typing import List, Optional
from langchain.tools import BaseTool
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.states.chatbotState import ChatbotState

load_dotenv()


class MoodDetectionNode:
    """
    Mood detection node that analyzes conversation to detect mood
    and updates it using MCP tools.
    """

    def __init__(self, llm, tools: Optional[List[BaseTool]] = None):
        """
        Initialize the mood detection node.

        Args:
            llm: The language model to use for mood detection
            tools: Optional list of tools (should include health_data tools)
        """
        self.llm = llm
        self.tools = tools or []

    async def _get_current_mood(self) -> Optional[str]:
        """
        Get current mood from JSON via MCP tool.

        Returns:
            Current mood or None
        """
        try:
            # Find the health_get_mood tool
            mood_tool = None
            for tool in self.tools:
                tool_name = None
                if hasattr(tool, "name"):
                    tool_name = tool.name
                elif isinstance(tool, dict):
                    tool_name = tool.get("name")

                if tool_name == "health_get_mood":
                    mood_tool = tool
                    break

            if mood_tool:
                # Call the tool
                if hasattr(mood_tool, "ainvoke"):
                    result = await mood_tool.ainvoke({})
                elif hasattr(mood_tool, "invoke"):
                    result = mood_tool.invoke({})
                else:
                    try:
                        result = await mood_tool({})
                    except:
                        result = mood_tool({})

                # Parse result
                if isinstance(result, str):
                    import json

                    try:
                        result_dict = json.loads(result)
                        return result_dict.get("mood", "").capitalize()
                    except:
                        return None
                elif isinstance(result, dict):
                    mood = result.get("mood", "")
                    return mood.capitalize() if mood else None

            return None
        except Exception as e:
            print(f"Error getting current mood: {e}")
            return None

    async def _detect_mood_from_conversation(self, messages: List) -> Optional[str]:
        """
        Use LLM to detect mood from the conversation context.
        Detects clear mood expressions from user messages.

        Args:
            messages: List of conversation messages

        Returns:
            Detected mood ("Happy", "Sad", "Surprised", "Angry") or None if mood cannot be determined
        """
        # Extract recent user messages for mood detection
        recent_messages = []
        for msg in messages[-3:]:  # Look at last 3 messages (more focused)
            if isinstance(msg, HumanMessage):
                recent_messages.append(f"User: {msg.content}")

        if not recent_messages:
            return None

        conversation_context = "\n".join(recent_messages)

        # Create a prompt for mood detection
        mood_detection_prompt = f"""Analyze the following user messages and determine the user's current mood.

User messages:
{conversation_context}

Detect mood if the user clearly expresses their emotional state, such as:
- Happy: joy, happiness, feeling good, positive emotions, "I am happy", "I feel happy", "I'm really happy"
- Sad: sadness, feeling down, disappointment, feeling bad, "I am sad", "I feel sad", "I'm really sad"
- Surprised: surprise, shock, amazement, disbelief, unexpected feelings, "I'm surprised", "I can't believe"
- Angry: anger, frustration, irritation, annoyance, "I am angry", "I feel angry", "I'm really angry"

Detect mood when:
- User explicitly states their mood (e.g., "I am happy", "I feel sad")
- User uses strong emotional language
- User clearly describes their emotional state

Do NOT detect mood for:
- Questions about mood (e.g., "How do I feel?")
- General conversation without emotional content
- Ambiguous statements

Respond with ONLY one word: Happy, Sad, Surprised, Angry, or None if the mood cannot be determined.
"""

        try:
            response = self.llm.invoke(mood_detection_prompt)
            mood = None

            if hasattr(response, "content"):
                mood_text = response.content.strip()
            elif isinstance(response, str):
                mood_text = response.strip()
            else:
                mood_text = str(response).strip()

            # Extract mood from response
            mood_text = mood_text.split()[0] if mood_text.split() else ""
            valid_moods = ["Happy", "Sad", "Surprised", "Angry"]

            for valid_mood in valid_moods:
                if valid_mood.lower() in mood_text.lower():
                    mood = valid_mood
                    break

            # Return detected mood or None
            return mood if mood else None
        except Exception as e:
            print(f"Error detecting mood: {e}")
            return None

    async def _update_mood_via_mcp(self, mood: str) -> bool:
        """
        Update mood using MCP tool.

        Args:
            mood: The mood to set ("Happy", "Sad", "Surprised", "Angry")

        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Find the health_update_mood tool from the tools list
            mood_tool = None
            for tool in self.tools:
                tool_name = None
                if hasattr(tool, "name"):
                    tool_name = tool.name
                elif hasattr(tool, "__name__"):
                    tool_name = tool.__name__
                elif isinstance(tool, dict):
                    tool_name = tool.get("name")

                if tool_name == "health_update_mood":
                    mood_tool = tool
                    break

            if mood_tool:
                # Call the tool using ainvoke for async tools
                if hasattr(mood_tool, "ainvoke"):
                    result = await mood_tool.ainvoke({"mood": mood})
                elif hasattr(mood_tool, "invoke"):
                    result = mood_tool.invoke({"mood": mood})
                else:
                    # Try calling directly
                    try:
                        result = await mood_tool({"mood": mood})
                    except:
                        result = mood_tool({"mood": mood})

                # Check if update was successful
                if isinstance(result, str):
                    import json

                    try:
                        result_dict = json.loads(result)
                        return result_dict.get("status") == "success"
                    except:
                        return (
                            "success" in result.lower() or "updated" in result.lower()
                        )
                elif isinstance(result, dict):
                    return result.get("status") == "success"

                return True
            else:
                print(
                    f"[Mood Detection] health_update_mood tool not found in {len(self.tools)} tools"
                )
                # List available tool names for debugging
                tool_names = []
                for tool in self.tools:
                    if hasattr(tool, "name"):
                        tool_names.append(tool.name)
                print(f"[Mood Detection] Available tools: {tool_names}")
                return False
        except Exception as e:
            print(f"Error updating mood via MCP: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def process(self, state: ChatbotState) -> dict:
        """
        Process the state to detect and update mood.
        Updates when mood is detected and different from current mood.

        Args:
            state: The chatbot state containing messages

        Returns:
            Updated state with mood information
        """
        messages = list(state.get("messages", []))

        # Only process if there are messages
        if not messages:
            return state

        # Get current mood first
        current_mood = await self._get_current_mood()

        # Detect mood from conversation
        detected_mood = await self._detect_mood_from_conversation(messages)

        if detected_mood:
            # Only update if mood is different from current mood
            if current_mood and detected_mood.lower() == current_mood.lower():
                # Same mood, no update needed
                return state

            # Update mood via MCP (when different)
            update_success = await self._update_mood_via_mcp(detected_mood)

            if update_success:
                print(
                    f"\n[Mood Detection] Mood detected: {detected_mood} (was: {current_mood}) - Updated via MCP\n"
                )
                # Return state with mood information
                return {**state, "detected_mood": detected_mood, "mood_updated": True}
            else:
                print(
                    f"\n[Mood Detection] Detected mood: {detected_mood} - Failed to update via MCP\n"
                )
                return {**state, "detected_mood": detected_mood, "mood_updated": False}
        # No mood detected - this is normal, don't log every time

        # Return state unchanged (mood update is side effect)
        return state


if __name__ == "__main__":
    import asyncio
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langchain_core.messages import HumanMessage, SystemMessage

    async def main():
        # Create LLM instance
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4o-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()

        # Create mood detection node
        node = MoodDetectionNode(llm)

        # Test state
        state = {
            "messages": [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(
                    content="I'm feeling really sad today, everything seems wrong."
                ),
            ]
        }

        # Process
        result = await node.process(state)
        print("Result:", result)

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
