from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./doctorbot.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    prescriptions = relationship("Prescription", back_populates="user")

class Prescription(Base):
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    extracted_text = Column(Text)
    processed_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="prescriptions")
    medications = relationship("Medication", back_populates="prescription")

class Medication(Base):
    __tablename__ = "medications"
    
    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"))
    name = Column(String, index=True)
    dosage = Column(String)
    frequency = Column(String)
    times_per_day = Column(Integer)
    instructions = Column(Text, nullable=True)
    
    prescription = relationship("Prescription", back_populates="medications")
    reminders = relationship("Reminder", back_populates="medication")

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"))
    scheduled_time = Column(String)  # Format: "HH:MM"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    medication = relationship("Medication", back_populates="reminders")

class Adherence(Base):
    __tablename__ = "adherence"
    
    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"))
    taken_at = Column(DateTime, nullable=True)
    confirmed = Column(Boolean, default=False)
    missed = Column(Boolean, default=False)
    
async def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()