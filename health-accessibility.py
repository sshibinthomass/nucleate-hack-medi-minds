# Healthcare Accessibility System - Modular Components

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import random

# ============================================================================
# DATA MODELS
# ============================================================================

class Specialty(Enum):
    CARDIOLOGY = "Cardiology"
    DERMATOLOGY = "Dermatology"
    PEDIATRICS = "Pediatrics"
    ORTHOPEDICS = "Orthopedics"
    NEUROLOGY = "Neurology"
    GENERAL_PRACTICE = "General Practice"
    PSYCHIATRY = "Psychiatry"
    ONCOLOGY = "Oncology"

@dataclass
class DoctorInfo:
    id: str
    name: str
    specialty: str
    hospital: str
    address: str
    gmap_link: str
    phone: str
    email: str
    languages: List[str]
    opening_time: str
    closing_time: str
    available_days: List[str]
    rating: float
    years_experience: int
    accepts_new_patients: bool
    
    def to_dict(self):
        return asdict(self)

@dataclass
class PatientInfo:
    id: str
    name: str
    date_of_birth: str
    gender: str
    phone: str
    email: str
    address: str
    emergency_contact: str
    emergency_phone: str
    blood_type: str
    allergies: List[str]
    chronic_conditions: List[str]
    current_medications: List[str]
    insurance_provider: str
    insurance_id: str
    
    def to_dict(self):
        return asdict(self)

@dataclass
class MedicalHistory:
    patient_id: str
    visit_date: str
    doctor_id: str
    doctor_name: str
    diagnosis: str
    symptoms: List[str]
    prescriptions: List[str]
    follow_up_required: bool
    follow_up_date: Optional[str]
    notes: str
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Appointment:
    id: str
    patient_id: str
    doctor_id: str
    date: str
    time: str
    reason: str
    status: str  # scheduled, completed, cancelled
    is_first_visit: bool
    created_at: str
    
    def to_dict(self):
        return asdict(self)

# ============================================================================
# MOCK DATA GENERATOR
# ============================================================================

class MockDataGenerator:
    """Generate realistic mock data for testing"""
    
    HOSPITALS = [
        ("City General Hospital", "123 Main St, Munich", "https://maps.google.com/?q=City+General+Hospital+Munich"),
        ("St. Mary's Medical Center", "456 Oak Ave, Munich", "https://maps.google.com/?q=St+Marys+Medical+Center+Munich"),
        ("University Hospital Munich", "789 University Blvd, Munich", "https://maps.google.com/?q=University+Hospital+Munich"),
        ("Downtown Clinic", "321 Center St, Munich", "https://maps.google.com/?q=Downtown+Clinic+Munich"),
    ]
    
    DOCTOR_NAMES = [
        "Dr. Anna Müller", "Dr. Thomas Schmidt", "Dr. Sarah Weber",
        "Dr. Michael Wagner", "Dr. Lisa Becker", "Dr. David Fischer",
        "Dr. Emma Klein", "Dr. Robert Wolf", "Dr. Julia Hoffmann"
    ]
    
    PATIENT_NAMES = [
        "Hans Gruber", "Maria Fischer", "Peter Schulz", "Anna Braun",
        "Klaus Meyer", "Sophie Wagner", "Felix Bauer", "Laura Koch"
    ]
    
    @staticmethod
    def generate_doctors(count: int = 20) -> List[DoctorInfo]:
        """Generate mock doctor data"""
        doctors = []
        specialties = [s.value for s in Specialty]
        
        for i in range(count):
            hospital, address, gmap = random.choice(MockDataGenerator.HOSPITALS)
            name = random.choice(MockDataGenerator.DOCTOR_NAMES)
            specialty = random.choice(specialties)
            
            doctor = DoctorInfo(
                id=f"DOC{str(i+1).zfill(4)}",
                name=f"{name} ({specialty[:4]})",
                specialty=specialty,
                hospital=hospital,
                address=address,
                gmap_link=gmap,
                phone=f"+49-89-{random.randint(1000000, 9999999)}",
                email=f"{name.lower().replace(' ', '.').replace('dr.', '')}@{hospital.lower().replace(' ', '').replace("'", '')}.de",
                languages=random.sample(["German", "English", "French", "Spanish", "Italian"], k=random.randint(2, 3)),
                opening_time=random.choice(["08:00", "09:00"]),
                closing_time=random.choice(["17:00", "18:00", "19:00"]),
                available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] if random.random() > 0.3 else ["Monday", "Wednesday", "Friday"],
                rating=round(random.uniform(3.5, 5.0), 1),
                years_experience=random.randint(5, 30),
                accepts_new_patients=random.choice([True, True, True, False])
            )
            doctors.append(doctor)
        
        return doctors
    
    @staticmethod
    def generate_patients(count: int = 10) -> List[PatientInfo]:
        """Generate mock patient data"""
        patients = []
        
        for i in range(count):
            name = random.choice(MockDataGenerator.PATIENT_NAMES)
            year = random.randint(1950, 2010)
            
            patient = PatientInfo(
                id=f"PAT{str(i+1).zfill(5)}",
                name=name,
                date_of_birth=f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                gender=random.choice(["Male", "Female", "Other"]),
                phone=f"+49-{random.randint(100, 999)}-{random.randint(1000000, 9999999)}",
                email=f"{name.lower().replace(' ', '.')}@email.de",
                address=f"{random.randint(1, 999)} {random.choice(['Main', 'Oak', 'Pine', 'Maple'])} St, Munich",
                emergency_contact=random.choice(MockDataGenerator.PATIENT_NAMES),
                emergency_phone=f"+49-{random.randint(100, 999)}-{random.randint(1000000, 9999999)}",
                blood_type=random.choice(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]),
                allergies=random.sample(["Penicillin", "Pollen", "Nuts", "Lactose", "None"], k=random.randint(0, 2)),
                chronic_conditions=random.sample(["Hypertension", "Diabetes", "Asthma", "None"], k=random.randint(0, 2)),
                current_medications=random.sample(["Aspirin", "Metformin", "Lisinopril", "None"], k=random.randint(0, 2)),
                insurance_provider=random.choice(["TK", "AOK", "Barmer", "DAK"]),
                insurance_id=f"INS{random.randint(100000, 999999)}"
            )
            patients.append(patient)
        
        return patients

# ============================================================================
# DOCTOR SEARCH & FILTER SERVICE
# ============================================================================

class DoctorSearchService:
    """Service for searching and filtering doctors"""
    
    def __init__(self, doctors: List[DoctorInfo]):
        self.doctors = doctors
    
    def search_by_specialty(self, specialty: str) -> List[DoctorInfo]:
        """Find doctors by specialty"""
        return [d for d in self.doctors if d.specialty.lower() == specialty.lower()]
    
    def search_by_hospital(self, hospital: str) -> List[DoctorInfo]:
        """Find doctors by hospital"""
        return [d for d in self.doctors if hospital.lower() in d.hospital.lower()]
    
    def search_by_language(self, language: str) -> List[DoctorInfo]:
        """Find doctors who speak a specific language"""
        return [d for d in self.doctors if language.lower() in [l.lower() for l in d.languages]]
    
    def search_accepting_new_patients(self) -> List[DoctorInfo]:
        """Find doctors accepting new patients"""
        return [d for d in self.doctors if d.accepts_new_patients]
    
    def search_nearby(self, location: str = "Munich") -> List[DoctorInfo]:
        """Find doctors in a specific location"""
        return [d for d in self.doctors if location.lower() in d.address.lower()]
    
    def advanced_search(self, 
                       specialty: Optional[str] = None,
                       language: Optional[str] = None,
                       hospital: Optional[str] = None,
                       accepts_new: bool = True,
                       min_rating: float = 0.0) -> List[DoctorInfo]:
        """Advanced search with multiple filters"""
        results = self.doctors
        
        if specialty:
            results = [d for d in results if d.specialty.lower() == specialty.lower()]
        if language:
            results = [d for d in results if language.lower() in [l.lower() for l in d.languages]]
        if hospital:
            results = [d for d in results if hospital.lower() in d.hospital.lower()]
        if accepts_new:
            results = [d for d in results if d.accepts_new_patients]
        
        results = [d for d in results if d.rating >= min_rating]
        
        # Sort by rating
        results.sort(key=lambda x: x.rating, reverse=True)
        
        return results

# ============================================================================
# APPOINTMENT BOOKING SERVICE
# ============================================================================

class AppointmentService:
    """Service for managing appointments"""
    
    def __init__(self):
        self.appointments: List[Appointment] = []
        self.medical_histories: List[MedicalHistory] = []
    
    def book_appointment(self, 
                        patient_id: str,
                        doctor_id: str,
                        date: str,
                        time: str,
                        reason: str,
                        is_first_visit: bool = False) -> Appointment:
        """Book a new appointment"""
        appointment = Appointment(
            id=f"APT{len(self.appointments)+1:05d}",
            patient_id=patient_id,
            doctor_id=doctor_id,
            date=date,
            time=time,
            reason=reason,
            status="scheduled",
            is_first_visit=is_first_visit,
            created_at=datetime.now().isoformat()
        )
        self.appointments.append(appointment)
        return appointment
    
    def get_patient_appointments(self, patient_id: str) -> List[Appointment]:
        """Get all appointments for a patient"""
        return [a for a in self.appointments if a.patient_id == patient_id]
    
    def get_doctor_appointments(self, doctor_id: str) -> List[Appointment]:
        """Get all appointments for a doctor"""
        return [a for a in self.appointments if a.doctor_id == doctor_id]
    
    def add_medical_history(self, history: MedicalHistory):
        """Add medical history record"""
        self.medical_histories.append(history)
    
    def get_patient_history(self, patient_id: str) -> List[MedicalHistory]:
        """Get medical history for a patient"""
        return [h for h in self.medical_histories if h.patient_id == patient_id]

# ============================================================================
# PATIENT-DOCTOR DATA SHARING SERVICE
# ============================================================================

class PatientDoctorShareService:
    """Service for sharing patient data with doctors"""
    
    def __init__(self, patients: List[PatientInfo], appointment_service: AppointmentService):
        self.patients = {p.id: p for p in patients}
        self.appointment_service = appointment_service
    
    def share_patient_info_for_appointment(self, appointment: Appointment) -> Dict[str, Any]:
        """
        Generate patient info package for doctor when appointment is booked.
        This includes full patient info for first visits, or summary for follow-ups.
        """
        patient = self.patients.get(appointment.patient_id)
        if not patient:
            return {"error": "Patient not found"}
        
        history = self.appointment_service.get_patient_history(appointment.patient_id)
        
        share_package = {
            "appointment_id": appointment.id,
            "appointment_date": appointment.date,
            "appointment_time": appointment.time,
            "reason_for_visit": appointment.reason,
            "is_first_visit": appointment.is_first_visit,
            "patient_info": patient.to_dict(),
            "medical_history": [h.to_dict() for h in history[-5:]],  # Last 5 visits
            "total_visits": len(history),
            "shared_at": datetime.now().isoformat()
        }
        
        return share_package

# ============================================================================
# DATA EXPORT SERVICE
# ============================================================================

class DataExportService:
    """Service for exporting data to JSON"""
    
    @staticmethod
    def export_doctors(doctors: List[DoctorInfo], filename: str = "doctors.json"):
        """Export doctors to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([d.to_dict() for d in doctors], f, indent=2, ensure_ascii=False)
        print(f"✓ Exported {len(doctors)} doctors to {filename}")
    
    @staticmethod
    def export_patients(patients: List[PatientInfo], filename: str = "patients.json"):
        """Export patients to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([p.to_dict() for p in patients], f, indent=2, ensure_ascii=False)
        print(f"✓ Exported {len(patients)} patients to {filename}")
    
    @staticmethod
    def export_appointments(appointments: List[Appointment], filename: str = "appointments.json"):
        """Export appointments to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([a.to_dict() for a in appointments], f, indent=2, ensure_ascii=False)
        print(f"✓ Exported {len(appointments)} appointments to {filename}")

# ============================================================================
# MAIN INTEGRATION CLASS
# ============================================================================

class HealthcareAccessibilitySystem:
    """
    Main system class that integrates all components.
    Use this as the primary interface for your LangGraph integration.
    """
    
    def __init__(self):
        # Initialize with mock data
        self.doctors = MockDataGenerator.generate_doctors(20)
        self.patients = MockDataGenerator.generate_patients(10)
        
        # Initialize services
        self.search_service = DoctorSearchService(self.doctors)
        self.appointment_service = AppointmentService()
        self.share_service = PatientDoctorShareService(self.patients, self.appointment_service)
        self.export_service = DataExportService()
    
    def get_doctor_search_service(self) -> DoctorSearchService:
        """Get doctor search service for agent integration"""
        return self.search_service
    
    def get_appointment_service(self) -> AppointmentService:
        """Get appointment service for agent integration"""
        return self.appointment_service
    
    def get_share_service(self) -> PatientDoctorShareService:
        """Get patient-doctor sharing service for agent integration"""
        return self.share_service
    
    def export_all_data(self):
        """Export all data to JSON files"""
        self.export_service.export_doctors(self.doctors)
        self.export_service.export_patients(self.patients)
        self.export_service.export_appointments(self.appointment_service.appointments)

# ============================================================================
# EXAMPLE USAGE & DEMO
# ============================================================================

def demo():
    """Demonstrate system functionality"""
    print("=" * 80)
    print("HEALTHCARE ACCESSIBILITY SYSTEM - DEMO")
    print("=" * 80)
    
    # Initialize system
    system = HealthcareAccessibilitySystem()
    
    # 1. Search for doctors
    print("\n1. SEARCHING FOR CARDIOLOGISTS IN MUNICH:")
    print("-" * 80)
    cardio_docs = system.search_service.search_by_specialty("Cardiology")
    for doc in cardio_docs[:3]:
        print(f"  • {doc.name} at {doc.hospital}")
        print(f"    Languages: {', '.join(doc.languages)}")
        print(f"    Hours: {doc.opening_time} - {doc.closing_time}")
        print(f"    Rating: {doc.rating}⭐ | Experience: {doc.years_experience} years")
        print(f"    Contact: {doc.phone} | {doc.email}")
        print()
    
    # 2. Advanced search
    print("\n2. ADVANCED SEARCH (English-speaking, accepting new patients, rating ≥ 4.0):")
    print("-" * 80)
    results = system.search_service.advanced_search(
        language="English",
        accepts_new=True,
        min_rating=4.0
    )
    for doc in results[:3]:
        print(f"  • {doc.name} - {doc.specialty} | {doc.rating}⭐")
    
    # 3. Book appointment
    print("\n3. BOOKING APPOINTMENT:")
    print("-" * 80)
    patient = system.patients[0]
    doctor = cardio_docs[0]
    
    appointment = system.appointment_service.book_appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        date="2025-11-20",
        time="10:00",
        reason="Regular checkup",
        is_first_visit=True
    )
    print(f"  ✓ Appointment booked: {appointment.id}")
    print(f"    Patient: {patient.name}")
    print(f"    Doctor: {doctor.name}")
    print(f"    Date/Time: {appointment.date} at {appointment.time}")
    
    # 4. Share patient info with doctor
    print("\n4. SHARING PATIENT INFO WITH DOCTOR:")
    print("-" * 80)
    share_package = system.share_service.share_patient_info_for_appointment(appointment)
    print(f"  ✓ Patient info shared for appointment {share_package['appointment_id']}")
    print(f"    Is first visit: {share_package['is_first_visit']}")
    print(f"    Patient: {share_package['patient_info']['name']}")
    print(f"    Allergies: {', '.join(share_package['patient_info']['allergies']) or 'None'}")
    print(f"    Previous visits: {share_package['total_visits']}")
    
    # 5. Export data
    print("\n5. EXPORTING DATA TO JSON FILES:")
    print("-" * 80)
    system.export_all_data()
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nJSON files generated: doctors.json, patients.json, appointments.json")
    print("\nIntegration with LangGraph:")
    print("  1. Import: from healthcare_system import HealthcareAccessibilitySystem")
    print("  2. Initialize: system = HealthcareAccessibilitySystem()")
    print("  3. Use services in your agents:")
    print("     - system.search_service.advanced_search(...)")
    print("     - system.appointment_service.book_appointment(...)")
    print("     - system.share_service.share_patient_info_for_appointment(...)")

if __name__ == "__main__":
    demo()