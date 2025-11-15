import os
import sys
import json
import aiohttp
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.graphs.graph_builder import GraphBuilder
from langgraph_agent.llms.groq_llm import GroqLLM
from langgraph_agent.llms.openai_llm import OpenAiLLM
from langgraph_agent.llms.gemini_llm import GeminiLLM
from langgraph_agent.llms.ollama_llm import OllamaLLM
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Load environment variables
load_dotenv()

# Global chatbot graph instance
chatbot_graph = None
# Global MCP tools (loaded once at startup)
mcp_tools = None
# In-memory session store: (session_id, use_case) -> list of LangChain messages
session_store: Dict[str, List] = {}


async def load_mcp_tools():
    """
    Load MCP tools once at startup. This function caches the tools
    so they're only loaded once and reused for all requests.
    Returns the list of tools that can be reused.
    """
    global mcp_tools
    if mcp_tools is not None:
        return mcp_tools  # Return cached tools if already loaded

    try:
        from langgraph_agent.nodes.mcp_chatbot_node import load_mcp_tools as load_tools

        # Load tools using the function from mcp_chatbot_node
        tools = await load_tools()

        mcp_tools = tools
        print(f"MCP tools loaded: {len(mcp_tools)} tools")
        return mcp_tools
    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        return []


async def load_tools_for_use_case(use_case: str):
    """
    Load appropriate tools based on the use case.

    Args:
        use_case: The use case identifier ("mcp_chatbot" or "doctor_chatbot")

    Returns:
        List of tools appropriate for the use case
    """
    if use_case == "doctor_chatbot":
        # Load doctor chatbot tools (patient specialist + Gmail only)
        try:
            from langgraph_agent.nodes.doctor_chatbot_node import (
                load_doctor_chatbot_tools,
            )

            tools = await load_doctor_chatbot_tools()
            print(f"Doctor chatbot tools loaded: {len(tools)} tools")
            return tools
        except Exception as e:
            print(f"Error loading doctor chatbot tools: {e}")
            return []
    else:
        # Default to regular MCP tools for mcp_chatbot
        return await load_mcp_tools()


async def initialize_chatbot():
    """Initialize the chatbot graph with OpenAI LLM"""
    global chatbot_graph
    try:
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4o-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()
        graph_builder = GraphBuilder(llm, user_controls_input)
        # Load MCP tools for initialization
        tools = await load_mcp_tools()
        chatbot_graph = await graph_builder.setup_graph("mcp_chatbot", tools=tools)
        return True
    except Exception as e:
        print(f"Error initializing chatbot: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    # Load MCP tools once at startup
    await load_mcp_tools()

    if not await initialize_chatbot():
        print(
            "Warning: Failed to initialize chatbot. API will still work but chatbot endpoints may fail."
        )

    # Fetch and update weather data on startup
    await update_weather_in_json()

    yield
    # Shutdown (if needed, add cleanup code here)
    # For example: cleanup resources, close connections, etc.


# Initialize FastAPI app
app = FastAPI(
    title="Medi-Mind Backend",
    description="FastAPI backend for the Medi-Mind medical assistant application",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


class SimpleChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    provider: Optional[str] = "openai"  # groq | openai | gemini | ollama
    selected_llm: Optional[str] = None
    use_case: Optional[str] = "mcp_chatbot"
    health_alerts: Optional[List[str]] = None


class ResetChatRequest(BaseModel):
    session_id: Optional[str] = "default"
    use_case: Optional[str] = "mcp_chatbot"


class UpdateWaterIntakeRequest(BaseModel):
    water_intake_cups: int


class UpdateMoodRequest(BaseModel):
    mood: str


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Medi-Mind Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "chatbot_initialized": chatbot_graph is not None}


@app.post("/chat", response_model=ChatResponse)
async def chat_simple(request: SimpleChatRequest):
    """
    Simple chat endpoint that takes a message.
    Conversation history is maintained on the backend per session_id.
    """
    if chatbot_graph is None:
        # Even if global init failed, we can still serve requests if provider creds are valid
        # so don't hard error here.
        pass

    try:
        # Choose LLM based on provider/model from request
        print("request-----", request)
        provider = (request.provider or "openai").lower()
        selected_llm = request.selected_llm
        if provider == "groq":
            user_controls_input = {
                "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
                "selected_llm": selected_llm or "openai/gpt-oss-20b",
            }
            llm = GroqLLM(user_controls_input).get_base_llm()
        elif provider == "openai":
            user_controls_input = {
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "selected_llm": selected_llm or "gpt-4o-mini",
            }
            llm = OpenAiLLM(user_controls_input).get_base_llm()
        elif provider == "gemini":
            user_controls_input = {
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "selected_llm": selected_llm or "gemini-2.5-flash",
            }
            llm = GeminiLLM(user_controls_input).get_base_llm()
        elif provider == "ollama":
            user_controls_input = {
                "selected_llm": selected_llm or "gemma3:1b",
                "OLLAMA_BASE_URL": os.getenv(
                    "OLLAMA_BASE_URL", "http://localhost:11434"
                ),
            }
            llm = OllamaLLM(user_controls_input).get_base_llm()
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {provider}"
            )

        use_case = request.use_case or "mcp_chatbot"

        # Build a lightweight graph for this request with the chosen LLM
        try:
            graph_builder = GraphBuilder(llm, {"selected_llm": selected_llm or ""})

            # Load appropriate tools based on use case
            tools = await load_tools_for_use_case(use_case)

            graph = await graph_builder.setup_graph(use_case, tools=tools)
        except ValueError as graph_error:
            raise HTTPException(status_code=400, detail=str(graph_error))

        # Resolve session and initialize store if needed
        session_id = request.session_id or "default"
        session_key = f"{session_id}::{use_case}"
        if session_key not in session_store:
            session_store[session_key] = []

        # Build system message with health alerts if present
        user_name = os.getenv("USER_NAME", "Patient")
        system_content = "You are Medi-Mind, a personal medical assistant. You help users manage their medical details, track health information, answer medical questions, and provide health-related guidance. Always be empathetic, professional, and prioritize user safety. Remind users that you are not a substitute for professional medical advice.\n\n"
        system_content += f"IMPORTANT - Email Functionality: When sending emails using the gmail_send_email tool, all emails are automatically sent to shibint85@gmail.com regardless of the recipient address specified. When sending emails, you MUST include patient details at the end of the email body in this format:\n\nPatient details:\n\nName: {user_name}\nContact: [Generate a random 10-digit US phone number in format +1XXXXXXXXXX]\n\nInform users that emails will be sent to shibint85@gmail.com for testing/security purposes."

        # Add health alerts to system message if present
        if request.health_alerts and len(request.health_alerts) > 0:
            alerts_text = "\n\n⚠️ HEALTH ALERTS - The following health metrics are below recommended levels:\n"
            alerts_text += "\n".join(f"  • {alert}" for alert in request.health_alerts)
            alerts_text += "\n\nPlease proactively help the user address these health concerns. Provide specific, actionable advice to help them improve these metrics. Be encouraging and supportive."
            system_content += alerts_text

        # Build messages from stored history and current input
        messages = [SystemMessage(content=system_content)]
        messages.extend(session_store[session_key])
        user_msg = HumanMessage(content=request.message)
        messages.append(user_msg)

        # Create state with all messages for context
        state = {"messages": messages}
        print("state-----", state)
        # Process with chatbot graph (use ainvoke for async graphs)
        result = await graph.ainvoke(state)
        # Extract response from graph result
        # The graph returns a state dict with messages, get the last message (should be AI response)
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
        else:
            response_text = "No response generated"

        # Persist history for this session (user + assistant)
        session_store[session_key].append(user_msg)
        session_store[session_key].append(AIMessage(content=response_text))

        return ChatResponse(response=response_text, status="success")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing chat request: {str(e)}"
        )


@app.post("/chat/reset")
async def reset_chat(request: ResetChatRequest):
    session_id = request.session_id or "default"
    use_case = request.use_case or "mcp_chatbot"
    session_key = f"{session_id}::{use_case}"
    session_store.pop(session_key, None)
    return {"status": "success"}


def get_personal_data_path():
    """Get the path to personal_data.json"""
    return (
        Path(__file__).parent
        / "langgraph_agent"
        / "mcps"
        / "json_data"
        / "personal_data.json"
    )


def get_patients_data_path():
    """Get the path to patients.json"""
    return (
        Path(__file__).parent
        / "langgraph_agent"
        / "mcps"
        / "json_data"
        / "patients.json"
    )


def get_uploaded_files_path():
    """Get the path to uploaded_files directory"""
    upload_dir = Path(__file__).parent / "uploaded_files"
    upload_dir.mkdir(exist_ok=True)
    return upload_dir


async def fetch_weather_data() -> Optional[Dict[str, float]]:
    """
    Fetch current weather data from OpenWeatherMap API.
    Falls back to wttr.in if OpenWeatherMap API key is not available.

    Returns:
        Dict with temperature_c, humidity_percent, wind_kmh or None if failed
    """
    try:
        # Try OpenWeatherMap first if API key is available
        openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
        city = os.getenv("WEATHER_CITY", "New York")  # Default city

        if openweather_api_key:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={openweather_api_key}&units=metric"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "temperature_c": round(data["main"]["temp"]),
                            "humidity_percent": data["main"]["humidity"],
                            "wind_kmh": round(
                                data["wind"]["speed"] * 3.6
                            ),  # Convert m/s to km/h
                        }

        # Fallback to wttr.in (free, no API key needed)
        url = f"https://wttr.in/{city}?format=j1"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get("current_condition", [{}])[0]
                    return {
                        "temperature_c": int(current.get("temp_C", 0)),
                        "humidity_percent": int(current.get("humidity", 0)),
                        "wind_kmh": int(float(current.get("windspeedKmph", 0))),
                    }
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None


async def update_weather_in_json():
    """Fetch weather data and update personal_data.json"""
    try:
        weather_data = await fetch_weather_data()
        if not weather_data:
            print("Warning: Could not fetch weather data. Using default values.")
            return

        personal_data_path = get_personal_data_path()

        # Read current data
        with open(personal_data_path, "r") as f:
            data = json.load(f)

        # Update weather fields
        data["temperature_c"] = weather_data["temperature_c"]
        data["humidity_percent"] = weather_data["humidity_percent"]
        data["wind_kmh"] = weather_data["wind_kmh"]

        # Write back to file
        with open(personal_data_path, "w") as f:
            json.dump(data, f, indent=6)

        print(
            f"Weather data updated: {weather_data['temperature_c']}°C, {weather_data['humidity_percent']}% humidity, {weather_data['wind_kmh']} km/h wind"
        )
    except Exception as e:
        print(f"Error updating weather in JSON: {e}")


def calculate_energy_level(mood: str, water_intake: float) -> int:
    """
    Calculate energy level based on mood and water intake.
    Formula: 60% mood + 40% water intake

    Args:
        mood: Current mood (Happy, Sad, Surprised, Angry)
        water_intake: Water intake in cups

    Returns:
        Energy level (0-100)
    """
    # Mood factor (0-100 scale)
    mood_factors = {
        "Happy": 90,
        "Surprised": 75,
        "Sad": 40,
        "Angry": 50,
    }
    mood_score = mood_factors.get(mood, 60)

    # Water intake factor (0-100 scale, optimal at 8 cups)
    optimal_water = 8
    water_deviation = abs((water_intake or 0) - optimal_water)
    water_score = max(0, min(100, 100 * (1 - water_deviation / optimal_water)))

    # Combined energy: 60% mood + 40% water
    energy = round(mood_score * 0.6 + water_score * 0.4)
    return max(0, min(100, energy))


def update_energy_in_json():
    """Read current data, calculate energy, and update JSON file"""
    try:
        personal_data_path = get_personal_data_path()

        # Read current data
        with open(personal_data_path, "r") as f:
            data = json.load(f)

        # Calculate energy based on current mood and water intake
        mood = data.get("mood", "Happy")
        water_intake = data.get("Water_Intake_cups", 0)
        energy_level = calculate_energy_level(mood, water_intake)

        # Update energy level
        data["Energy_Level"] = energy_level

        # Write back to file
        with open(personal_data_path, "w") as f:
            json.dump(data, f, indent=6)

        return energy_level
    except Exception as e:
        print(f"Error updating energy level: {e}")
        return None


@app.get("/doctor-statistics")
async def get_doctor_statistics():
    """
    Get statistics for doctor dashboard:
    - Total number of patients
    - Allergies with patient counts
    - Age groups (less than 20, 20-40, more than 40)
    """
    try:
        patients_path = get_patients_data_path()

        if not patients_path.exists():
            return {
                "total_patients": 0,
                "allergies": {},
                "age_groups": {"less_than_20": 0, "20_to_40": 0, "more_than_40": 0},
            }

        with open(patients_path, "r", encoding="utf-8") as f:
            patients = json.load(f)

        # Calculate total patients
        total_patients = len(patients)

        # Calculate allergies with patient counts
        allergies_count = {}
        for patient in patients:
            allergies = patient.get("allergies", [])
            for allergy in allergies:
                if allergy and allergy != "None":
                    allergies_count[allergy] = allergies_count.get(allergy, 0) + 1

        # Calculate age groups
        from datetime import datetime

        age_groups = {"less_than_20": 0, "20_to_40": 0, "more_than_40": 0}

        current_year = datetime.now().year
        for patient in patients:
            dob_str = patient.get("date_of_birth", "")
            if dob_str:
                try:
                    # Parse date of birth (format: YYYY-MM-DD)
                    birth_year = int(dob_str.split("-")[0])
                    age = current_year - birth_year

                    if age < 20:
                        age_groups["less_than_20"] += 1
                    elif age <= 40:
                        age_groups["20_to_40"] += 1
                    else:
                        age_groups["more_than_40"] += 1
                except (ValueError, IndexError):
                    # Skip invalid dates
                    pass

        return {
            "total_patients": total_patients,
            "allergies": allergies_count,
            "age_groups": age_groups,
        }
    except Exception as e:
        print(f"Error getting doctor statistics: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Error getting doctor statistics: {str(e)}"
        )


@app.get("/personal-data")
async def get_personal_data():
    """Get personal health data from JSON file"""
    try:
        personal_data_path = get_personal_data_path()
        with open(personal_data_path, "r") as f:
            data = json.load(f)
        # Add city name from environment variable
        data["city"] = os.getenv("WEATHER_CITY", "New York")
        # Add user name from environment variable
        data["user_name"] = os.getenv("USER_NAME", "User")
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Personal data file not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading personal data: {str(e)}"
        )


@app.put("/personal-data/water-intake")
async def update_water_intake(request: UpdateWaterIntakeRequest):
    """Update water intake in personal data JSON file and recalculate energy"""
    try:
        personal_data_path = get_personal_data_path()

        # Read current data
        with open(personal_data_path, "r") as f:
            data = json.load(f)

        # Update water intake
        data["Water_Intake_cups"] = request.water_intake_cups

        # Recalculate and update energy level
        mood = data.get("mood", "Happy")
        energy_level = calculate_energy_level(mood, request.water_intake_cups)
        data["Energy_Level"] = energy_level

        # Write back to file
        with open(personal_data_path, "w") as f:
            json.dump(data, f, indent=6)

        return {
            "status": "success",
            "water_intake_cups": request.water_intake_cups,
            "energy_level": energy_level,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Personal data file not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating water intake: {str(e)}"
        )


@app.put("/personal-data/mood")
async def update_mood(request: UpdateMoodRequest):
    """Update mood in personal data JSON file and recalculate energy"""
    try:
        valid_moods = ["Happy", "Sad", "Surprised", "Angry"]
        mood_capitalized = request.mood.capitalize()

        if mood_capitalized not in valid_moods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mood. Must be one of: {', '.join(valid_moods)}",
            )

        personal_data_path = get_personal_data_path()

        # Read current data
        with open(personal_data_path, "r") as f:
            data = json.load(f)

        # Update mood
        data["mood"] = mood_capitalized

        # Recalculate and update energy level
        water_intake = data.get("Water_Intake_cups", 0)
        energy_level = calculate_energy_level(mood_capitalized, water_intake)
        data["Energy_Level"] = energy_level

        # Write back to file
        with open(personal_data_path, "w") as f:
            json.dump(data, f, indent=6)

        return {
            "status": "success",
            "mood": mood_capitalized,
            "energy_level": energy_level,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Personal data file not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating mood: {str(e)}")


@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and save it to the uploaded_files directory"""
    try:
        upload_dir = get_uploaded_files_path()

        # Create a safe filename (prevent directory traversal)
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Sanitize filename
        safe_filename = os.path.basename(filename)
        file_path = upload_dir / safe_filename

        # Handle duplicate files by adding a number suffix
        counter = 1
        original_path = file_path
        while file_path.exists():
            name, ext = os.path.splitext(safe_filename)
            file_path = upload_dir / f"{name}_{counter}{ext}"
            counter += 1

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "status": "success",
            "filename": file_path.name,
            "path": str(file_path.relative_to(Path(__file__).parent)),
            "size": file_path.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


def main():
    """Main function to run the FastAPI server"""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
