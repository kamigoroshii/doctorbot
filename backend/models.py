from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, time

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str
    times_per_day: int
    schedule_times: List[str]  # e.g., ["08:00", "20:00"]
    instructions: Optional[str] = None
    duration: Optional[str] = None
    confidence: Optional[float] = None
    source_line: Optional[str] = None
    matched_by: Optional[str] = None

class MedicationSchedule(BaseModel):
    medications: List[Medication]
    total_medications: int

class ExtractedEntity(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: Optional[str] = None
    instructions: Optional[str] = None
    confidence: Optional[float] = None
    source_line: Optional[str] = None
    matched_by: Optional[str] = None

class ExtractionSummary(BaseModel):
    method: str
    confidence: float
    entity_count: int
    entities: List[ExtractedEntity]
    
class DrugWarning(BaseModel):
    severity: str  # "high", "medium", "low"
    message: str
    affected_medications: List[str]

class FDAAlert(BaseModel):
    type: str  # "recall", "safety_alert", "adverse_event", "label_warning"
    severity: str
    title: str
    message: str
    date: Optional[str] = None
    action_required: Optional[str] = None
    source: Optional[str] = "FDA"

class PrescriptionResponse(BaseModel):
    success: bool
    extracted_text: str
    medication_schedule: MedicationSchedule
    warnings: List[DrugWarning]
    safety_score: Optional[int] = None
    recommendations: Optional[List[str]] = None
    fda_alerts: Optional[Dict[str, Any]] = None
    extraction_method: Optional[str] = None
    extraction_confidence: Optional[float] = None
    extraction_summary: Optional[ExtractionSummary] = None

class ReminderRequest(BaseModel):
    user_id: str
    medication_name: str
    dosage: str
    scheduled_time: str
    
class UserProfile(BaseModel):
    telegram_user_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    created_at: datetime
    active_prescriptions: int = 0
    notification_preferences: Optional[Dict[str, bool]] = None

class NotificationPreferences(BaseModel):
    immediate_alerts: bool = True
    daily_digest: bool = True
    weekly_summary: bool = True
    fda_recalls: bool = True
    drug_interactions: bool = True
    medication_reminders: bool = True