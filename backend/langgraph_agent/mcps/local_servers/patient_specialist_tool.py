import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("patient_specialist")

# Get the path to patients.json
current_file = Path(__file__).resolve()
# Go up from local_servers -> mcps -> langgraph_agent -> backend
# Then add mcps/json_data/patients.json
mcps_dir = current_file.parent.parent  # backend/langgraph_agent/mcps
patients_json_path = mcps_dir / "json_data" / "patients.json"


class PatientDatabase:
    def __init__(self):
        self.patients: List[Dict[str, Any]] = []
        self._load_patients()

    def _load_patients(self) -> None:
        """Load patients data from JSON file."""
        try:
            if patients_json_path.exists():
                with open(patients_json_path, "r", encoding="utf-8") as f:
                    self.patients = json.load(f)
                print(
                    f"Successfully loaded {len(self.patients)} patients from {patients_json_path}"
                )
            else:
                print(f"Warning: patients.json not found at {patients_json_path}")
                self.patients = []
        except Exception as e:
            print(f"Error loading patients.json: {e}")
            import traceback

            traceback.print_exc()
            self.patients = []

    def search_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Search patients by name (case-insensitive partial match)."""
        if not self.patients:
            return []
        name_lower = name.lower()
        return [
            patient
            for patient in self.patients
            if name_lower in patient.get("name", "").lower()
        ]

    def search_by_id(self, patient_id: str) -> List[Dict[str, Any]]:
        """Search patients by ID (case-insensitive)."""
        if not self.patients:
            return []
        patient_id_upper = patient_id.upper()
        return [
            patient
            for patient in self.patients
            if patient_id_upper == patient.get("id", "").upper()
        ]

    def search_by_blood_type(self, blood_type: str) -> List[Dict[str, Any]]:
        """Search patients by blood type (case-insensitive)."""
        if not self.patients:
            return []
        blood_type_upper = blood_type.upper()
        return [
            patient
            for patient in self.patients
            if blood_type_upper == patient.get("blood_type", "").upper()
        ]

    def search_by_allergy(self, allergy: str) -> List[Dict[str, Any]]:
        """Search patients with a specific allergy (case-insensitive partial match)."""
        if not self.patients:
            return []
        allergy_lower = allergy.lower()
        return [
            patient
            for patient in self.patients
            if any(
                allergy_lower in allergy_item.lower()
                for allergy_item in patient.get("allergies", [])
            )
        ]

    def search_by_chronic_condition(self, condition: str) -> List[Dict[str, Any]]:
        """Search patients with a specific chronic condition (case-insensitive partial match)."""
        if not self.patients:
            return []
        condition_lower = condition.lower()
        return [
            patient
            for patient in self.patients
            if any(
                condition_lower in cond.lower()
                for cond in patient.get("chronic_conditions", [])
            )
        ]

    def search_by_medication(self, medication: str) -> List[Dict[str, Any]]:
        """Search patients taking a specific medication (case-insensitive partial match)."""
        if not self.patients:
            return []
        medication_lower = medication.lower()
        return [
            patient
            for patient in self.patients
            if any(
                medication_lower in med.lower()
                for med in patient.get("current_medications", [])
            )
        ]

    def search_by_insurance_provider(self, provider: str) -> List[Dict[str, Any]]:
        """Search patients by insurance provider (case-insensitive partial match)."""
        if not self.patients:
            return []
        provider_lower = provider.lower()
        return [
            patient
            for patient in self.patients
            if provider_lower in patient.get("insurance_provider", "").lower()
        ]

    def search_by_address(self, address: str) -> List[Dict[str, Any]]:
        """Search patients by address (case-insensitive partial match)."""
        if not self.patients:
            return []
        address_lower = address.lower()
        return [
            patient
            for patient in self.patients
            if address_lower in patient.get("address", "").lower()
        ]

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific patient by their ID."""
        if not self.patients:
            return None
        for patient in self.patients:
            if patient.get("id", "").upper() == patient_id.upper():
                return patient
        return None

    def get_all_blood_types(self) -> List[str]:
        """Get a list of all unique blood types."""
        if not self.patients:
            return []
        blood_types = set()
        for patient in self.patients:
            blood_type = patient.get("blood_type")
            if blood_type:
                blood_types.add(blood_type)
        return sorted(list(blood_types))

    def get_all_chronic_conditions(self) -> List[str]:
        """Get a list of all unique chronic conditions."""
        if not self.patients:
            return []
        conditions = set()
        for patient in self.patients:
            for condition in patient.get("chronic_conditions", []):
                if condition and condition != "None":
                    conditions.add(condition)
        return sorted(list(conditions))

    def advanced_search(
        self,
        name: Optional[str] = None,
        patient_id: Optional[str] = None,
        blood_type: Optional[str] = None,
        allergy: Optional[str] = None,
        chronic_condition: Optional[str] = None,
        medication: Optional[str] = None,
        insurance_provider: Optional[str] = None,
        address: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Advanced search with multiple filters. All filters are AND conditions."""
        if not self.patients:
            return []

        results = self.patients.copy()

        if name:
            results = [
                patient
                for patient in results
                if name.lower() in patient.get("name", "").lower()
            ]

        if patient_id:
            results = [
                patient
                for patient in results
                if patient_id.upper() == patient.get("id", "").upper()
            ]

        if blood_type:
            results = [
                patient
                for patient in results
                if blood_type.upper() == patient.get("blood_type", "").upper()
            ]

        if allergy:
            results = [
                patient
                for patient in results
                if any(
                    allergy.lower() in allergy_item.lower()
                    for allergy_item in patient.get("allergies", [])
                )
            ]

        if chronic_condition:
            results = [
                patient
                for patient in results
                if any(
                    chronic_condition.lower() in cond.lower()
                    for cond in patient.get("chronic_conditions", [])
                )
            ]

        if medication:
            results = [
                patient
                for patient in results
                if any(
                    medication.lower() in med.lower()
                    for med in patient.get("current_medications", [])
                )
            ]

        if insurance_provider:
            results = [
                patient
                for patient in results
                if insurance_provider.lower()
                in patient.get("insurance_provider", "").lower()
            ]

        if address:
            results = [
                patient
                for patient in results
                if address.lower() in patient.get("address", "").lower()
            ]

        return results

    def save_patients(self) -> bool:
        """Save patients data back to JSON file."""
        try:
            with open(patients_json_path, "w", encoding="utf-8") as f:
                json.dump(self.patients, f, indent=2, ensure_ascii=False)
                f.flush()  # Ensure data is written immediately
                import os

                os.fsync(f.fileno())  # Force write to disk
            print(
                f"Successfully saved {len(self.patients)} patients to {patients_json_path}"
            )
            return True
        except Exception as e:
            print(f"Error saving patients.json: {e}")
            import traceback

            traceback.print_exc()
            return False

    def update_patient_by_id(
        self,
        patient_id: str,
        name: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        emergency_contact: Optional[str] = None,
        emergency_phone: Optional[str] = None,
        blood_type: Optional[str] = None,
        allergies: Optional[List[str]] = None,
        chronic_conditions: Optional[List[str]] = None,
        current_medications: Optional[List[str]] = None,
        insurance_provider: Optional[str] = None,
        insurance_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a patient's information by ID. Only updates provided fields."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        # Update only provided fields
        if name is not None:
            patient["name"] = name
        if date_of_birth is not None:
            patient["date_of_birth"] = date_of_birth
        if gender is not None:
            patient["gender"] = gender
        if phone is not None:
            patient["phone"] = phone
        if email is not None:
            patient["email"] = email
        if address is not None:
            patient["address"] = address
        if emergency_contact is not None:
            patient["emergency_contact"] = emergency_contact
        if emergency_phone is not None:
            patient["emergency_phone"] = emergency_phone
        if blood_type is not None:
            patient["blood_type"] = blood_type
        if allergies is not None:
            patient["allergies"] = allergies
        if chronic_conditions is not None:
            patient["chronic_conditions"] = chronic_conditions
        if current_medications is not None:
            patient["current_medications"] = current_medications
        if insurance_provider is not None:
            patient["insurance_provider"] = insurance_provider
        if insurance_id is not None:
            patient["insurance_id"] = insurance_id

        # Save to file
        if self.save_patients():
            return patient
        return None

    def add_allergy_to_patient(
        self, patient_id: str, allergy: str
    ) -> Optional[Dict[str, Any]]:
        """Add an allergy to a patient's allergy list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        allergies = patient.get("allergies", [])
        if allergy not in allergies:
            allergies.append(allergy)
            patient["allergies"] = allergies
            if self.save_patients():
                return patient
        return patient

    def remove_allergy_from_patient(
        self, patient_id: str, allergy: str
    ) -> Optional[Dict[str, Any]]:
        """Remove an allergy from a patient's allergy list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        allergies = patient.get("allergies", [])
        if allergy in allergies:
            allergies.remove(allergy)
            patient["allergies"] = allergies
            if self.save_patients():
                return patient
        return patient

    def add_chronic_condition_to_patient(
        self, patient_id: str, condition: str
    ) -> Optional[Dict[str, Any]]:
        """Add a chronic condition to a patient's conditions list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        conditions = patient.get("chronic_conditions", [])
        if condition not in conditions:
            conditions.append(condition)
            patient["chronic_conditions"] = conditions
            if self.save_patients():
                return patient
        return patient

    def remove_chronic_condition_from_patient(
        self, patient_id: str, condition: str
    ) -> Optional[Dict[str, Any]]:
        """Remove a chronic condition from a patient's conditions list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        conditions = patient.get("chronic_conditions", [])
        if condition in conditions:
            conditions.remove(condition)
            patient["chronic_conditions"] = conditions
            if self.save_patients():
                return patient
        return patient

    def add_medication_to_patient(
        self, patient_id: str, medication: str
    ) -> Optional[Dict[str, Any]]:
        """Add a medication to a patient's current medications list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        medications = patient.get("current_medications", [])
        if medication not in medications:
            medications.append(medication)
            patient["current_medications"] = medications
            if self.save_patients():
                return patient
        return patient

    def remove_medication_from_patient(
        self, patient_id: str, medication: str
    ) -> Optional[Dict[str, Any]]:
        """Remove a medication from a patient's current medications list."""
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        medications = patient.get("current_medications", [])
        if medication in medications:
            medications.remove(medication)
            patient["current_medications"] = medications
            if self.save_patients():
                return patient
        return patient


# Initialize the database
patient_db = PatientDatabase()


@mcp.tool()
async def patient_search_by_name(name: str) -> str:
    """Search for patients by their name.

    This tool helps find patients based on their name. The search is case-insensitive and supports partial matches.

    Args:
        name: The patient's name or part of the name to search for (e.g., 'Anna', 'Braun', 'Hans').

    Returns:
        A JSON string containing a list of patients matching the name, including their ID, name, contact info, medical details, and insurance information.
    """
    results = patient_db.search_by_name(name)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_id(patient_id: str) -> str:
    """Search for patients by their patient ID.

    This tool helps find a specific patient by searching their unique patient ID. The search is case-insensitive.

    Args:
        patient_id: The patient's ID (e.g., 'PAT00001', 'PAT00002').

    Returns:
        A JSON string containing a list of patients matching the ID, including their complete information.
    """
    results = patient_db.search_by_id(patient_id)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_blood_type(blood_type: str) -> str:
    """Search for patients by their blood type.

    This tool helps find all patients with a specific blood type (e.g., 'A+', 'O-', 'AB-').

    Args:
        blood_type: The blood type to search for (e.g., 'A+', 'O-', 'AB-').

    Returns:
        A JSON string containing a list of patients with that blood type, including their ID, name, and medical information.
    """
    results = patient_db.search_by_blood_type(blood_type)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_allergy(allergy: str) -> str:
    """Search for patients with a specific allergy.

    This tool helps find all patients who have a particular allergy (e.g., 'Penicillin', 'Lactose', 'Nuts').

    Args:
        allergy: The allergy to search for (e.g., 'Penicillin', 'Lactose', 'Nuts', 'Pollen').

    Returns:
        A JSON string containing a list of patients with that allergy, including their ID, name, and medical information.
    """
    results = patient_db.search_by_allergy(allergy)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_chronic_condition(condition: str) -> str:
    """Search for patients with a specific chronic condition.

    This tool helps find all patients who have a particular chronic condition (e.g., 'Diabetes', 'Hypertension', 'Asthma').

    Args:
        condition: The chronic condition to search for (e.g., 'Diabetes', 'Hypertension', 'Asthma').

    Returns:
        A JSON string containing a list of patients with that condition, including their ID, name, and medical information.
    """
    results = patient_db.search_by_chronic_condition(condition)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_medication(medication: str) -> str:
    """Search for patients taking a specific medication.

    This tool helps find all patients who are currently taking a particular medication (e.g., 'Metformin', 'Aspirin', 'Lisinopril').

    Args:
        medication: The medication to search for (e.g., 'Metformin', 'Aspirin', 'Lisinopril').

    Returns:
        A JSON string containing a list of patients taking that medication, including their ID, name, and medical information.
    """
    results = patient_db.search_by_medication(medication)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_insurance_provider(provider: str) -> str:
    """Search for patients by their insurance provider.

    This tool helps find all patients covered by a specific insurance provider (e.g., 'AOK', 'TK', 'DAK', 'Barmer').

    Args:
        provider: The insurance provider name (e.g., 'AOK', 'TK', 'DAK', 'Barmer').

    Returns:
        A JSON string containing a list of patients with that insurance provider, including their ID, name, and insurance information.
    """
    results = patient_db.search_by_insurance_provider(provider)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_search_by_address(address: str) -> str:
    """Search for patients by their address or location.

    This tool helps find patients based on their address or location (e.g., 'Munich', 'Main St', 'Pine St').

    Args:
        address: The address, city, or location to search for (e.g., 'Munich', 'Main St', 'Pine St').

    Returns:
        A JSON string containing a list of patients in that location, including their ID, name, address, and contact information.
    """
    results = patient_db.search_by_address(address)
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_get_by_id(patient_id: str) -> str:
    """Get detailed information about a specific patient by their ID.

    This tool retrieves complete information for a specific patient when you know their ID (e.g., 'PAT00001').

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001', 'PAT00002').

    Returns:
        A JSON string containing the complete patient information including ID, name, date of birth, contact info, medical history, allergies, medications, and insurance details.
    """
    patient = patient_db.get_patient_by_id(patient_id)
    if patient:
        return json.dumps(patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_get_all_blood_types() -> str:
    """Get a list of all unique blood types in the patient database.

    This tool helps discover what blood types are present in the patient database.

    Returns:
        A JSON string containing a list of all unique blood types available in the patient database.
    """
    blood_types = patient_db.get_all_blood_types()
    return json.dumps(blood_types, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_get_all_chronic_conditions() -> str:
    """Get a list of all unique chronic conditions in the patient database.

    This tool helps discover what chronic conditions are present in the patient database.

    Returns:
        A JSON string containing a list of all unique chronic conditions available in the patient database.
    """
    conditions = patient_db.get_all_chronic_conditions()
    return json.dumps(conditions, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_advanced_search(
    name: Optional[str] = None,
    patient_id: Optional[str] = None,
    blood_type: Optional[str] = None,
    allergy: Optional[str] = None,
    chronic_condition: Optional[str] = None,
    medication: Optional[str] = None,
    insurance_provider: Optional[str] = None,
    address: Optional[str] = None,
) -> str:
    """Advanced search for patients with multiple filters.

    This is the most powerful search tool that allows combining multiple criteria to find specific patients.
    All provided filters are combined with AND logic (patient must match all specified criteria).
    You can provide any combination of filters - at least one filter should be provided.

    Args:
        name: Filter by patient's name (partial match supported).
        patient_id: Filter by patient ID (exact match).
        blood_type: Filter by blood type (exact match, e.g., 'A+', 'O-').
        allergy: Filter by allergy (partial match, e.g., 'Penicillin', 'Lactose').
        chronic_condition: Filter by chronic condition (partial match, e.g., 'Diabetes', 'Hypertension').
        medication: Filter by medication (partial match, e.g., 'Metformin', 'Aspirin').
        insurance_provider: Filter by insurance provider (partial match, e.g., 'AOK', 'TK').
        address: Filter by address/location (partial match, e.g., 'Munich', 'Main St').

    Returns:
        A JSON string containing a list of patients matching all the specified criteria, including their complete information.
    """
    results = patient_db.advanced_search(
        name=name,
        patient_id=patient_id,
        blood_type=blood_type,
        allergy=allergy,
        chronic_condition=chronic_condition,
        medication=medication,
        insurance_provider=insurance_provider,
        address=address,
    )
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def patient_update_by_id(
    patient_id: str,
    name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    gender: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact: Optional[str] = None,
    emergency_phone: Optional[str] = None,
    blood_type: Optional[str] = None,
    allergies: Optional[List[str]] = None,
    chronic_conditions: Optional[List[str]] = None,
    current_medications: Optional[List[str]] = None,
    insurance_provider: Optional[str] = None,
    insurance_id: Optional[str] = None,
) -> str:
    """Update a patient's information by their ID.

    This tool allows doctors to update any field of a patient's record. Only the fields you provide will be updated.
    All other fields will remain unchanged.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001', 'PAT00002').
        name: Update patient's name.
        date_of_birth: Update date of birth (format: 'YYYY-MM-DD').
        gender: Update gender ('Male', 'Female', 'Other').
        phone: Update phone number.
        email: Update email address.
        address: Update address.
        emergency_contact: Update emergency contact name.
        emergency_phone: Update emergency contact phone.
        blood_type: Update blood type (e.g., 'A+', 'O-', 'AB-').
        allergies: Replace entire allergies list with new list.
        chronic_conditions: Replace entire chronic conditions list with new list.
        current_medications: Replace entire current medications list with new list.
        insurance_provider: Update insurance provider name.
        insurance_id: Update insurance ID.

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.update_patient_by_id(
        patient_id=patient_id,
        name=name,
        date_of_birth=date_of_birth,
        gender=gender,
        phone=phone,
        email=email,
        address=address,
        emergency_contact=emergency_contact,
        emergency_phone=emergency_phone,
        blood_type=blood_type,
        allergies=allergies,
        chronic_conditions=chronic_conditions,
        current_medications=current_medications,
        insurance_provider=insurance_provider,
        insurance_id=insurance_id,
    )
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_add_allergy(patient_id: str, allergy: str) -> str:
    """Add an allergy to a patient's allergy list.

    This tool adds a new allergy to a patient's existing allergies without removing other allergies.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        allergy: The allergy to add (e.g., 'Penicillin', 'Lactose', 'Nuts').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.add_allergy_to_patient(patient_id, allergy)
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_remove_allergy(patient_id: str, allergy: str) -> str:
    """Remove an allergy from a patient's allergy list.

    This tool removes a specific allergy from a patient's allergies list.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        allergy: The allergy to remove (e.g., 'Penicillin', 'Lactose').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.remove_allergy_from_patient(patient_id, allergy)
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_add_chronic_condition(patient_id: str, condition: str) -> str:
    """Add a chronic condition to a patient's conditions list.

    This tool adds a new chronic condition to a patient's existing conditions without removing other conditions.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        condition: The chronic condition to add (e.g., 'Diabetes', 'Hypertension', 'Asthma').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.add_chronic_condition_to_patient(patient_id, condition)
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_remove_chronic_condition(patient_id: str, condition: str) -> str:
    """Remove a chronic condition from a patient's conditions list.

    This tool removes a specific chronic condition from a patient's conditions list.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        condition: The chronic condition to remove (e.g., 'Diabetes', 'Hypertension').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.remove_chronic_condition_from_patient(
        patient_id, condition
    )
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_add_medication(patient_id: str, medication: str) -> str:
    """Add a medication to a patient's current medications list.

    This tool adds a new medication to a patient's current medications without removing other medications.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        medication: The medication to add (e.g., 'Metformin', 'Aspirin', 'Lisinopril').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.add_medication_to_patient(patient_id, medication)
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


@mcp.tool()
async def patient_remove_medication(patient_id: str, medication: str) -> str:
    """Remove a medication from a patient's current medications list.

    This tool removes a specific medication from a patient's current medications list.

    Args:
        patient_id: The unique patient ID (e.g., 'PAT00001').
        medication: The medication to remove (e.g., 'Metformin', 'Aspirin').

    Returns:
        A JSON string containing the updated patient information, or an error message if patient not found.
    """
    updated_patient = patient_db.remove_medication_from_patient(patient_id, medication)
    if updated_patient:
        return json.dumps(updated_patient, indent=2, ensure_ascii=False)
    else:
        return json.dumps(
            {"error": f"Patient with ID '{patient_id}' not found"}, indent=2
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
