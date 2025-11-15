import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("doctor_specialist")

# Get the path to doctors.json
current_file = Path(__file__).resolve()
# Go up from local_servers -> mcps -> langgraph_agent -> backend
# Then add mcps/json_data/doctors.json
mcps_dir = current_file.parent.parent  # backend/langgraph_agent/mcps
doctors_json_path = mcps_dir / "json_data" / "doctors.json"


class DoctorDatabase:
    def __init__(self):
        self.doctors: List[Dict[str, Any]] = []
        self._load_doctors()

    def _load_doctors(self) -> None:
        """Load doctors data from JSON file."""
        try:
            if doctors_json_path.exists():
                with open(doctors_json_path, "r", encoding="utf-8") as f:
                    self.doctors = json.load(f)
                print(
                    f"Successfully loaded {len(self.doctors)} doctors from {doctors_json_path}"
                )
            else:
                print(f"Warning: doctors.json not found at {doctors_json_path}")
                self.doctors = []
        except Exception as e:
            print(f"Error loading doctors.json: {e}")
            import traceback

            traceback.print_exc()
            self.doctors = []

    def search_by_specialty(self, specialty: str) -> List[Dict[str, Any]]:
        """Search doctors by specialty (case-insensitive partial match)."""
        if not self.doctors:
            return []
        specialty_lower = specialty.lower()
        return [
            doc
            for doc in self.doctors
            if specialty_lower in doc.get("specialty", "").lower()
        ]

    def search_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Search doctors by name (case-insensitive partial match)."""
        if not self.doctors:
            return []
        name_lower = name.lower()
        return [
            doc for doc in self.doctors if name_lower in doc.get("name", "").lower()
        ]

    def search_by_hospital(self, hospital: str) -> List[Dict[str, Any]]:
        """Search doctors by hospital name (case-insensitive partial match)."""
        if not self.doctors:
            return []
        hospital_lower = hospital.lower()
        return [
            doc
            for doc in self.doctors
            if hospital_lower in doc.get("hospital", "").lower()
        ]

    def search_by_location(self, location: str) -> List[Dict[str, Any]]:
        """Search doctors by address/location (case-insensitive partial match)."""
        if not self.doctors:
            return []
        location_lower = location.lower()
        return [
            doc
            for doc in self.doctors
            if location_lower in doc.get("address", "").lower()
        ]

    def search_by_language(self, language: str) -> List[Dict[str, Any]]:
        """Search doctors who speak a specific language (case-insensitive)."""
        if not self.doctors:
            return []
        language_lower = language.lower()
        return [
            doc
            for doc in self.doctors
            if any(language_lower in lang.lower() for lang in doc.get("languages", []))
        ]

    def search_by_rating(self, min_rating: float) -> List[Dict[str, Any]]:
        """Search doctors with rating greater than or equal to min_rating."""
        if not self.doctors:
            return []
        return [doc for doc in self.doctors if doc.get("rating", 0) >= min_rating]

    def search_accepting_new_patients(
        self, accepting: bool = True
    ) -> List[Dict[str, Any]]:
        """Search doctors who are accepting (or not accepting) new patients."""
        if not self.doctors:
            return []
        return [
            doc
            for doc in self.doctors
            if doc.get("accepts_new_patients", False) == accepting
        ]

    def search_by_available_day(self, day: str) -> List[Dict[str, Any]]:
        """Search doctors available on a specific day (e.g., 'Monday', 'Tuesday')."""
        if not self.doctors:
            return []
        day_lower = day.lower()
        return [
            doc
            for doc in self.doctors
            if any(
                day_lower == available_day.lower()
                for available_day in doc.get("available_days", [])
            )
        ]

    def get_doctor_by_id(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific doctor by their ID."""
        if not self.doctors:
            return None
        for doc in self.doctors:
            if doc.get("id", "").upper() == doctor_id.upper():
                return doc
        return None

    def get_all_specialties(self) -> List[str]:
        """Get a list of all unique specialties."""
        if not self.doctors:
            return []
        specialties = set()
        for doc in self.doctors:
            specialty = doc.get("specialty")
            if specialty:
                specialties.add(specialty)
        return sorted(list(specialties))

    def advanced_search(
        self,
        specialty: Optional[str] = None,
        name: Optional[str] = None,
        hospital: Optional[str] = None,
        location: Optional[str] = None,
        language: Optional[str] = None,
        min_rating: Optional[float] = None,
        accepts_new_patients: Optional[bool] = None,
        available_day: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Advanced search with multiple filters. All filters are AND conditions."""
        if not self.doctors:
            return []

        results = self.doctors.copy()

        if specialty:
            results = [
                doc
                for doc in results
                if specialty.lower() in doc.get("specialty", "").lower()
            ]

        if name:
            results = [
                doc for doc in results if name.lower() in doc.get("name", "").lower()
            ]

        if hospital:
            results = [
                doc
                for doc in results
                if hospital.lower() in doc.get("hospital", "").lower()
            ]

        if location:
            results = [
                doc
                for doc in results
                if location.lower() in doc.get("address", "").lower()
            ]

        if language:
            results = [
                doc
                for doc in results
                if any(
                    language.lower() in lang.lower()
                    for lang in doc.get("languages", [])
                )
            ]

        if min_rating is not None:
            results = [doc for doc in results if doc.get("rating", 0) >= min_rating]

        if accepts_new_patients is not None:
            results = [
                doc
                for doc in results
                if doc.get("accepts_new_patients", False) == accepts_new_patients
            ]

        if available_day:
            results = [
                doc
                for doc in results
                if any(
                    available_day.lower() == day.lower()
                    for day in doc.get("available_days", [])
                )
            ]

        return results


# Initialize the database
doctor_db = DoctorDatabase()


@mcp.tool()
async def doctor_search_by_specialty(specialty: str) -> str:
    """Search for doctors by their medical specialty.

    This tool helps find doctors based on their area of specialization (e.g., 'Cardiology', 'Pediatrics', 'Orthopedics').
    The search is case-insensitive and supports partial matches.

    Args:
        specialty: The medical specialty to search for (e.g., 'Cardiology', 'General Practice', 'Pediatrics').

    Returns:
        A JSON string containing a list of doctors matching the specialty, including their ID, name, hospital, contact info, and availability.
    """
    results = doctor_db.search_by_specialty(specialty)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_name(name: str) -> str:
    """Search for doctors by their name.

    This tool helps find a specific doctor by searching their name. The search is case-insensitive and supports partial matches.

    Args:
        name: The doctor's name or part of the name to search for (e.g., 'Anna', 'Müller', 'Dr. Emma').

    Returns:
        A JSON string containing a list of doctors matching the name, including their ID, specialty, hospital, contact info, and availability.
    """
    results = doctor_db.search_by_name(name)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_hospital(hospital: str) -> str:
    """Search for doctors working at a specific hospital.

    This tool helps find all doctors associated with a particular hospital or clinic.
    The search is case-insensitive and supports partial matches.

    Args:
        hospital: The name of the hospital or clinic (e.g., 'University Hospital', 'Downtown Clinic').

    Returns:
        A JSON string containing a list of doctors at that hospital, including their ID, name, specialty, contact info, and availability.
    """
    results = doctor_db.search_by_hospital(hospital)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_location(location: str) -> str:
    """Search for doctors by their location or address.

    This tool helps find doctors based on their practice location or address.
    The search is case-insensitive and supports partial matches (e.g., 'Munich', 'University Blvd').

    Args:
        location: The location, city, or address to search for (e.g., 'Munich', 'Downtown', 'University Blvd').

    Returns:
        A JSON string containing a list of doctors in that location, including their ID, name, specialty, hospital, contact info, and availability.
    """
    results = doctor_db.search_by_location(location)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_language(language: str) -> str:
    """Search for doctors who speak a specific language.

    This tool helps find doctors who can communicate in a particular language, which is useful for patients who prefer consultations in their native language.

    Args:
        language: The language to search for (e.g., 'English', 'German', 'French', 'Spanish', 'Italian').

    Returns:
        A JSON string containing a list of doctors who speak that language, including their ID, name, specialty, hospital, contact info, and availability.
    """
    results = doctor_db.search_by_language(language)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_rating(min_rating: float) -> str:
    """Search for doctors with a minimum rating.

    This tool helps find highly-rated doctors. Ratings are typically on a scale of 0-5.

    Args:
        min_rating: The minimum rating threshold (e.g., 4.0 for doctors rated 4.0 or higher).

    Returns:
        A JSON string containing a list of doctors meeting the rating criteria, sorted by rating (highest first), including their ID, name, specialty, hospital, contact info, and availability.
    """
    results = doctor_db.search_by_rating(min_rating)
    # Sort by rating descending
    results.sort(key=lambda x: x.get("rating", 0), reverse=True)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_accepting_new_patients(accepting: bool = True) -> str:
    """Search for doctors who are accepting (or not accepting) new patients.

    This tool helps find doctors who are currently accepting new patients, which is important for patients looking to establish care with a new doctor.

    Args:
        accepting: True to find doctors accepting new patients, False to find doctors not accepting new patients. Defaults to True.

    Returns:
        A JSON string containing a list of doctors based on their new patient acceptance status, including their ID, name, specialty, hospital, contact info, and availability.
    """
    results = doctor_db.search_accepting_new_patients(accepting)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_search_by_available_day(day: str) -> str:
    """Search for doctors available on a specific day of the week.

    This tool helps find doctors who are available for appointments on a particular day.

    Args:
        day: The day of the week (e.g., 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday').

    Returns:
        A JSON string containing a list of doctors available on that day, including their ID, name, specialty, hospital, contact info, and availability schedule.
    """
    results = doctor_db.search_by_available_day(day)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_get_by_id(doctor_id: str) -> str:
    """Get detailed information about a specific doctor by their ID.

    This tool retrieves complete information for a specific doctor when you know their ID (e.g., 'DOC0001').

    Args:
        doctor_id: The unique doctor ID (e.g., 'DOC0001', 'DOC0002').

    Returns:
        A JSON string containing the complete doctor information including ID, name, specialty, hospital, address, contact info, languages, schedule, rating, experience, and new patient acceptance status.
    """
    doctor = doctor_db.get_doctor_by_id(doctor_id)
    if doctor:
        return json.dumps(doctor, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Doctor with ID '{doctor_id}' not found"}, indent=2
        )


@mcp.tool()
async def doctor_get_all_specialties() -> str:
    """Get a list of all available medical specialties in the database.

    This tool helps discover what medical specialties are available, which can be useful for patients who need to find a specialist.

    Returns:
        A JSON string containing a list of all unique medical specialties available in the doctor database.
    """
    specialties = doctor_db.get_all_specialties()
    return json.dumps(specialties, indent=2, ensure_ascii=False)


@mcp.tool()
async def doctor_advanced_search(
    specialty: Optional[str] = None,
    name: Optional[str] = None,
    hospital: Optional[str] = None,
    location: Optional[str] = None,
    language: Optional[str] = None,
    min_rating: Optional[float] = None,
    accepts_new_patients: Optional[bool] = None,
    available_day: Optional[str] = None,
) -> str:
    """Advanced search for doctors with multiple filters.

    This is the most powerful search tool that allows combining multiple criteria to find the perfect doctor.
    All provided filters are combined with AND logic (doctor must match all specified criteria).
    You can provide any combination of filters - at least one filter should be provided.

    Args:
        specialty: Filter by medical specialty (e.g., 'Cardiology', 'Pediatrics').
        name: Filter by doctor's name (partial match supported).
        hospital: Filter by hospital name (partial match supported).
        location: Filter by location/address (partial match supported).
        language: Filter by spoken language (e.g., 'English', 'German').
        min_rating: Minimum rating threshold (e.g., 4.0).
        accepts_new_patients: True to find doctors accepting new patients, False otherwise, None to ignore this filter.
        available_day: Filter by day of week when doctor is available (e.g., 'Monday', 'Friday').

    Returns:
        A JSON string containing a list of doctors matching all the specified criteria, including their complete information.
    """
    results = doctor_db.advanced_search(
        specialty=specialty,
        name=name,
        hospital=hospital,
        location=location,
        language=language,
        min_rating=min_rating,
        accepts_new_patients=accepts_new_patients,
        available_day=available_day,
    )
    return json.dumps(results, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
