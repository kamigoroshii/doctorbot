from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import traceback
from dotenv import load_dotenv
import PyPDF2
import docx
import io

from .models import PrescriptionResponse, MedicationSchedule
from .services.ocr_service import OCRService
from .services.ai_service import AIService
from .services.drug_checker import DrugInteractionChecker
from .database import init_db

load_dotenv()

app = FastAPI(title="DoctorBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
ocr_service = OCRService()
ai_service = AIService()
drug_checker = DrugInteractionChecker()

def _raise_processing_exception(error: Exception) -> None:
    """Map backend processing failures to appropriate HTTP responses."""
    if isinstance(error, HTTPException):
        raise error

    error_message = str(error)
    lowered = error_message.lower()

    if any(token in lowered for token in ["api key", "invalid_key", "rejected", "401", "403", "quota", "rate limit"]):
        raise HTTPException(status_code=503, detail=error_message)

    raise HTTPException(status_code=500, detail=error_message)

@app.on_event("startup")
async def startup_event():
    await init_db()

async def extract_text_from_pdf(pdf_data: bytes) -> str:
    """Extract text from PDF document"""
    try:
        pdf_file = io.BytesIO(pdf_data)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text.strip()
    except Exception as e:
        raise Exception(f"PDF text extraction failed: {str(e)}")

async def extract_text_from_word(doc_data: bytes) -> str:
    """Extract text from Word document"""
    try:
        doc_file = io.BytesIO(doc_data)
        doc = docx.Document(doc_file)
        
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text.strip()
    except Exception as e:
        raise Exception(f"Word document text extraction failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "DoctorBot API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint: verifies backend is up and AI API key is valid"""
    try:
        key_status = await ai_service.validate_api_key()
        ai_ok = key_status.get("status") == "ok"
        return {
            "status": "ok",
            "ai_status": key_status.get("status"),
            "ai_provider": key_status.get("provider"),
            "credits": key_status.get("credits", "N/A"),
            "detail": key_status.get("detail", "")
        }
    except Exception as e:
        return {
            "status": "degraded",
            "ai_status": "error",
            "ai_provider": os.getenv("AI_PROVIDER", "unknown"),
            "credits": "Unknown",
            "detail": str(e)
        }

@app.post("/process-prescription", response_model=PrescriptionResponse)
async def process_prescription(file: UploadFile = File(...)):
    """Process uploaded prescription image and return comprehensive medication analysis"""
    try:
        # Read uploaded image
        image_data = await file.read()

        # First try direct image parsing via Gemini Vision (if GOOGLE_API_KEY is configured).
        print("🔄 Step 1: Trying Gemini Vision direct image parse...")
        medication_schedule = await ai_service.parse_prescription_from_image(image_data)
        if medication_schedule and medication_schedule.total_medications > 0:
            extracted_text = "[Parsed directly from image with Gemini Vision fallback]"
            print(f"✅ Step 1 done: Gemini Vision found {medication_schedule.total_medications} medication(s)")
        else:
            # Fallback to OCR text extraction + parser pipeline.
            print("🔄 Step 2: Running OCR text extraction...")
            extracted_text = await ocr_service.extract_text(image_data)
            print(f"✅ Step 2 done: OCR extracted text (len={len(extracted_text)})")

            if extracted_text == "__OCR_FAILED__":
                raise HTTPException(
                    status_code=422,
                    detail="__OCR_FAILED__"
                )
            print("🔄 Step 3: Running AI prescription parser...")
            medication_schedule = await ai_service.parse_prescription(extracted_text)
            print(f"✅ Step 3 done: AI found {medication_schedule.total_medications} medication(s)")
        
        # Comprehensive safety check with FDA integration
        print("🔄 Step 4: Running comprehensive safety check...")
        try:
            safety_results = await drug_checker.comprehensive_safety_check(medication_schedule.medications)
            print(f"✅ Step 4 done: safety_score={safety_results.get('safety_score')}")
        except Exception as safety_err:
            print(f"⚠️ Safety check failed ({type(safety_err).__name__}: {safety_err}) – returning empty safety results")
            safety_results = {
                "interaction_warnings": [],
                "fda_alerts": [],
                "categorized_notifications": {},
                "safety_score": 100,
                "recommendations": ["⚠️ Safety check could not be completed. Please consult your doctor or pharmacist."]
            }

        # Combine all warnings
        all_warnings = safety_results["interaction_warnings"] + safety_results["fda_alerts"]

        print("🔄 Step 5: Building PrescriptionResponse...")
        try:
            response = PrescriptionResponse(
                success=True,
                extracted_text=extracted_text,
                medication_schedule=medication_schedule,
                warnings=all_warnings,
                safety_score=safety_results["safety_score"],
                recommendations=safety_results["recommendations"],
                fda_alerts=safety_results["categorized_notifications"]
            )
        except Exception as build_err:
            print(f"❌ Step 5 FAILED building PrescriptionResponse: {type(build_err).__name__}: {build_err}")
            traceback.print_exc()
            raise build_err
        print("✅ Step 5 done: Response built successfully")
        return response

    except Exception as e:
        print(f"❌ /process-prescription FAILED")
        print(f"❌ Exception type: {type(e).__name__}")
        print(f"❌ Exception message: {str(e)}")
        print("❌ Full traceback:")
        traceback.print_exc()
        _raise_processing_exception(e)

@app.post("/process-document", response_model=PrescriptionResponse)
async def process_document(file: UploadFile = File(...)):
    """Process uploaded prescription document (PDF, DOC, etc.) and return medication schedule"""
    try:
        # Read uploaded document
        document_data = await file.read()
        
        # Extract text based on file type
        if file.content_type == "application/pdf":
            extracted_text = await extract_text_from_pdf(document_data)
        elif file.content_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            extracted_text = await extract_text_from_word(document_data)
        elif file.content_type == "text/plain":
            extracted_text = document_data.decode('utf-8')
        elif file.content_type in ["image/jpeg", "image/png"]:
            # Fallback to OCR for images sent as documents
            extracted_text = await ocr_service.extract_text(document_data)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="No readable text found in the uploaded document")

        # Parse text using AI
        medication_schedule = await ai_service.parse_prescription(extracted_text)
        
        # Use the same comprehensive safety flow as image uploads
        safety_results = await drug_checker.comprehensive_safety_check(medication_schedule.medications)
        all_warnings = safety_results["interaction_warnings"] + safety_results["fda_alerts"]
        
        return PrescriptionResponse(
            success=True,
            extracted_text=extracted_text,
            medication_schedule=medication_schedule,
            warnings=all_warnings,
            safety_score=safety_results["safety_score"],
            recommendations=safety_results["recommendations"],
            fda_alerts=safety_results["categorized_notifications"]
        )
        
    except Exception as e:
        _raise_processing_exception(e)

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True
    )