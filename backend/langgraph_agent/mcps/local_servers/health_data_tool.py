import json
from pathlib import Path
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("health_data")

# Get the path to personal_data.json
current_file = Path(__file__).resolve()
mcps_dir = current_file.parent.parent  # backend/langgraph_agent/mcps
personal_data_path = mcps_dir / "json_data" / "personal_data.json"


class HealthDataManager:
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load health data from JSON file."""
        try:
            if personal_data_path.exists():
                with open(personal_data_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                print(f"Successfully loaded health data from {personal_data_path}")
            else:
                print(f"Warning: personal_data.json not found at {personal_data_path}")
                self.data = {}
        except Exception as e:
            print(f"Error loading personal_data.json: {e}")
            import traceback

            traceback.print_exc()
            self.data = {}

    def _save_data(self) -> bool:
        """Save health data to JSON file."""
        try:
            with open(personal_data_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=6, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving personal_data.json: {e}")
            import traceback

            traceback.print_exc()
            return False

    def get_health_data(self) -> Dict[str, Any]:
        """Get all health data."""
        self._load_data()  # Reload to get latest data
        return self.data

    def _calculate_energy_level(self, mood: str, water_intake: float) -> int:
        """
        Calculate energy level based on mood and water intake.
        Formula: 60% mood + 40% water intake
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

    def update_water_intake(self, cups: int) -> Dict[str, Any]:
        """Update water intake and save to file."""
        self._load_data()  # Get latest data first
        self.data["Water_Intake_cups"] = max(0, cups)  # Ensure non-negative

        # Recalculate and update energy level
        mood = self.data.get("mood", "Happy")
        energy_level = self._calculate_energy_level(mood, cups)
        self.data["Energy_Level"] = energy_level

        if self._save_data():
            return {
                "status": "success",
                "message": f"Water intake updated to {cups} cups",
                "Water_Intake_cups": self.data["Water_Intake_cups"],
                "Energy_Level": energy_level,
            }
        else:
            return {"status": "error", "message": "Failed to save water intake update"}

    def increment_water_intake(self, cups: int = 1) -> Dict[str, Any]:
        """Increment water intake by specified cups."""
        self._load_data()
        current = self.data.get("Water_Intake_cups", 0)
        new_value = current + cups
        return self.update_water_intake(new_value)

    def decrement_water_intake(self, cups: int = 1) -> Dict[str, Any]:
        """Decrement water intake by specified cups."""
        self._load_data()
        current = self.data.get("Water_Intake_cups", 0)
        new_value = max(0, current - cups)
        return self.update_water_intake(new_value)

    def update_mood(self, mood: str) -> Dict[str, Any]:
        """Update mood and save to file."""
        valid_moods = ["Happy", "Sad", "Surprised", "Angry"]
        mood_capitalized = mood.capitalize()

        if mood_capitalized not in valid_moods:
            return {
                "status": "error",
                "message": f"Invalid mood. Must be one of: {', '.join(valid_moods)}",
                "valid_moods": valid_moods,
            }

        self._load_data()  # Get latest data first
        self.data["mood"] = mood_capitalized

        # Recalculate and update energy level
        water_intake = self.data.get("Water_Intake_cups", 0)
        energy_level = self._calculate_energy_level(mood_capitalized, water_intake)
        self.data["Energy_Level"] = energy_level

        if self._save_data():
            return {
                "status": "success",
                "message": f"Mood updated to {mood_capitalized}",
                "mood": self.data["mood"],
                "Energy_Level": energy_level,
            }
        else:
            return {"status": "error", "message": "Failed to save mood update"}


# Initialize the manager
health_manager = HealthDataManager()


@mcp.tool()
async def health_get_all_data() -> str:
    """Get all personal health data including steps, calories, blood oxygen, heart rate, water intake, and more.

    This tool retrieves the complete current health metrics for the user.

    Returns:
        A JSON string containing all health data metrics.
    """
    data = health_manager.get_health_data()
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_update_water_intake(cups: int) -> str:
    """Update the user's water intake to a specific number of cups.

    This tool sets the water intake to an exact value. Use this when the user tells you
    they've had a specific amount of water or want to set their daily intake.

    Args:
        cups: The number of cups of water to set (must be non-negative integer).

    Returns:
        A JSON string with the status of the update and the new water intake value.
    """
    result = health_manager.update_water_intake(cups)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_add_water_intake(cups: int = 1) -> str:
    """Add cups of water to the user's current water intake.

    This tool increments the water intake by the specified amount. Use this when
    the user tells you they just drank some water or want to log additional water consumption.

    Args:
        cups: The number of cups to add to current water intake (default is 1).

    Returns:
        A JSON string with the status of the update and the new water intake value.
    """
    result = health_manager.increment_water_intake(cups)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_remove_water_intake(cups: int = 1) -> str:
    """Remove cups of water from the user's current water intake.

    This tool decrements the water intake by the specified amount. Use this when
    the user made a mistake and wants to correct their water intake.

    Args:
        cups: The number of cups to remove from current water intake (default is 1).

    Returns:
        A JSON string with the status of the update and the new water intake value.
    """
    result = health_manager.decrement_water_intake(cups)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_get_water_intake() -> str:
    """Get the current water intake value.

    This tool retrieves only the water intake information.

    Returns:
        A JSON string with the current water intake in cups.
    """
    data = health_manager.get_health_data()
    result = {"Water_Intake_cups": data.get("Water_Intake_cups", 0), "unit": "cups"}
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_update_mood(mood: str) -> str:
    """Update the user's mood.

    This tool updates the user's current mood. The mood must be one of: Happy, Sad, Surprised, or Angry.
    Use this when the user tells you how they're feeling or wants to update their mood.

    Args:
        mood: The mood to set. Must be one of: "Happy", "Sad", "Surprised", or "Angry" (case-insensitive).

    Returns:
        A JSON string with the status of the update and the new mood value.
    """
    result = health_manager.update_mood(mood)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def health_get_mood() -> str:
    """Get the current mood value.

    This tool retrieves only the mood information.

    Returns:
        A JSON string with the current mood.
    """
    data = health_manager.get_health_data()
    result = {
        "mood": data.get("mood", ""),
        "valid_moods": ["Happy", "Sad", "Surprised", "Angry"],
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
