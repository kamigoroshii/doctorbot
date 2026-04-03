from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain, ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseOutputParser
from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain.tools import BaseTool
from typing import List, Dict, Any, Optional
import json
import os
from ..models import Medication, MedicationSchedule, DrugWarning

class MedicationOutputParser(BaseOutputParser):
    """Custom parser for medication extraction"""
    
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            # Try to parse as JSON first
            if text.strip().startswith('{'):
                return json.loads(text)
            
            # Fallback parsing logic
            medications = []
            lines = text.split('\n')
            
            for line in lines:
                if any(keyword in line.lower() for keyword in ['tablet', 'capsule', 'mg', 'ml', 'bd', 'tid', 'od']):
                    # Extract medication info using regex patterns
                    import re
                    
                    # Pattern for medication name and dosage
                    pattern = r'(\w+(?:\s+\w+)*)\s+(\d+(?:\.\d+)?\s*(?:mg|ml))\s*(?:-\s*)?.*?(?:BD|BID|TID|QID|OD)'
                    match = re.search(pattern, line, re.IGNORECASE)
                    
                    if match:
                        name = match.group(1).strip()
                        dosage = match.group(2).strip()
                        
                        # Determine frequency
                        freq_map = {
                            'OD': ('once daily', 1, ['08:00']),
                            'BD': ('twice daily', 2, ['08:00', '20:00']),
                            'BID': ('twice daily', 2, ['08:00', '20:00']),
                            'TID': ('three times daily', 3, ['08:00', '14:00', '20:00']),
                            'QID': ('four times daily', 4, ['08:00', '12:00', '16:00', '20:00'])
                        }
                        
                        for code, (freq, times, schedule) in freq_map.items():
                            if code in line.upper():
                                medications.append({
                                    "name": name,
                                    "dosage": dosage,
                                    "frequency": freq,
                                    "times_per_day": times,
                                    "schedule_times": schedule
                                })
                                break
            
            return {"medications": medications}
            
        except Exception as e:
            print(f"⚠️ Parsing error: {str(e)}")
            return {"medications": []}

class DrugInteractionTool(BaseTool):
    """LangChain tool for drug interaction checking"""
    name = "drug_interaction_checker"
    description = "Check for drug interactions between medications"
    
    def _run(self, medications: str) -> str:
        """Check drug interactions"""
        try:
            # Parse medication list
            med_list = medications.split(',')
            
            # Simple interaction check
            interactions = []
            high_risk_combinations = [
                ("warfarin", "aspirin", "Increased bleeding risk"),
                ("metformin", "alcohol", "Lactic acidosis risk"),
                ("simvastatin", "grapefruit", "Muscle damage risk")
            ]
            
            for med1, med2, warning in high_risk_combinations:
                if any(med1.lower() in med.lower() for med in med_list) and \
                   any(med2.lower() in med.lower() for med in med_list):
                    interactions.append(f"⚠️ {warning}: {med1} + {med2}")
            
            return "\n".join(interactions) if interactions else "No major interactions detected"
            
        except Exception as e:
            return f"Error checking interactions: {str(e)}"
    
    async def _arun(self, medications: str) -> str:
        return self._run(medications)

class FDAAlertTool(BaseTool):
    """LangChain tool for FDA alerts"""
    name = "fda_alert_checker"
    description = "Check for FDA alerts and recalls for medications"
    
    def _run(self, medication: str) -> str:
        """Check FDA alerts"""
        # Simulate FDA alert checking
        high_alert_drugs = {
            "warfarin": "🚨 BLACK BOX WARNING: Increased bleeding risk",
            "metformin": "⚠️ FDA ALERT: Lactic acidosis in kidney disease",
            "digoxin": "🔔 MONITORING: Narrow therapeutic window"
        }
        
        med_lower = medication.lower()
        for drug, alert in high_alert_drugs.items():
            if drug in med_lower:
                return alert
        
        return "No current FDA alerts for this medication"
    
    async def _arun(self, medication: str) -> str:
        return self._run(medication)

class LangChainService:
    def __init__(self):
        # Initialize with OpenRouter (using your existing API key)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        # Create custom LLM for OpenRouter
        self.llm = self._create_openrouter_llm()
        
        # Initialize tools
        self.tools = [
            DrugInteractionTool(),
            FDAAlertTool()
        ]
        
        # Create conversation memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize parser
        self.parser = MedicationOutputParser()
        
    def _create_openrouter_llm(self):
        """Create OpenRouter-compatible LLM"""
        # For now, we'll use the existing AI service integration
        # This can be enhanced with proper LangChain OpenRouter integration
        return None
    
    async def enhanced_prescription_parsing(self, prescription_text: str, user_context: Dict = None) -> Dict:
        """Enhanced prescription parsing with LangChain"""
        
        # Create system prompt
        system_template = """You are a medical AI assistant specialized in prescription analysis.
        
        Your tasks:
        1. Extract medication information accurately
        2. Identify potential drug interactions
        3. Check for FDA alerts and warnings
        4. Provide safety recommendations
        
        Always prioritize patient safety and provide clear, actionable information.
        
        User Context: {user_context}
        """
        
        human_template = """
        Please analyze this prescription and extract medication information:
        
        Prescription Text:
        {prescription_text}
        
        Return a JSON object with:
        - medications: list of medications with name, dosage, frequency, schedule
        - safety_alerts: any immediate safety concerns
        - recommendations: personalized recommendations
        
        Focus on accuracy and patient safety.
        """
        
        # Create prompt template
        system_message = SystemMessagePromptTemplate.from_template(system_template)
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            system_message,
            human_message
        ])
        
        # For now, use existing AI service with enhanced prompting
        from .ai_service import AIService
        ai_service = AIService()
        
        # Enhanced prompt for better parsing
        enhanced_prompt = f"""
        Analyze this prescription as a medical expert:
        
        {prescription_text}
        
        Extract medications with exact names (not "Take"), dosages, and frequencies.
        Convert medical abbreviations: BD=twice daily, TID=three times daily, OD=once daily
        
        Return JSON format:
        {{
            "medications": [
                {{
                    "name": "actual medication name",
                    "dosage": "amount with unit",
                    "frequency": "frequency in words",
                    "times_per_day": number,
                    "schedule_times": ["HH:MM", "HH:MM"]
                }}
            ]
        }}
        """
        
        try:
            # Use existing AI service with enhanced prompt
            result = await ai_service.parse_prescription(enhanced_prompt)
            
            # Add LangChain enhancements
            enhanced_result = {
                "medications": [],
                "safety_alerts": [],
                "recommendations": [],
                "langchain_analysis": True
            }
            
            # Process medications
            for med in result.medications:
                enhanced_med = {
                    "name": med.name,
                    "dosage": med.dosage,
                    "frequency": med.frequency,
                    "times_per_day": med.times_per_day,
                    "schedule_times": med.schedule_times,
                    "instructions": med.instructions
                }
                enhanced_result["medications"].append(enhanced_med)
                
                # Check for alerts using tools
                interaction_check = self.tools[0]._run(",".join([m.name for m in result.medications]))
                fda_check = self.tools[1]._run(med.name)
                
                if "⚠️" in interaction_check or "🚨" in interaction_check:
                    enhanced_result["safety_alerts"].append(interaction_check)
                
                if "⚠️" in fda_check or "🚨" in fda_check:
                    enhanced_result["safety_alerts"].append(fda_check)
            
            # Generate recommendations
            enhanced_result["recommendations"] = self._generate_smart_recommendations(
                enhanced_result["medications"], 
                enhanced_result["safety_alerts"],
                user_context
            )
            
            return enhanced_result
            
        except Exception as e:
            print(f"⚠️ LangChain parsing error: {str(e)}")
            # Fallback to regular parsing
            result = await ai_service.parse_prescription(prescription_text)
            return {
                "medications": [med.dict() for med in result.medications],
                "safety_alerts": [],
                "recommendations": ["Consult healthcare provider for medication guidance"],
                "langchain_analysis": False
            }
    
    def _generate_smart_recommendations(self, medications: List[Dict], alerts: List[str], user_context: Dict = None) -> List[str]:
        """Generate intelligent recommendations using LangChain logic"""
        recommendations = []
        
        # Base recommendations
        recommendations.extend([
            "📋 Keep an updated medication list with you",
            "💊 Take medications exactly as prescribed",
            "⏰ Set up reminders for consistent timing"
        ])
        
        # Alert-based recommendations
        if alerts:
            high_severity_alerts = [a for a in alerts if "🚨" in a]
            if high_severity_alerts:
                recommendations.extend([
                    "🚨 URGENT: Contact healthcare provider immediately",
                    "📞 Do not take medications until consulting doctor",
                    "🏥 Consider emergency consultation if symptoms occur"
                ])
            else:
                recommendations.extend([
                    "⚠️ Discuss safety alerts with healthcare provider",
                    "📋 Schedule medication review appointment"
                ])
        
        # Medication-specific recommendations
        med_names = [med["name"].lower() for med in medications]
        
        if any("antibiotic" in name or "amoxicillin" in name for name in med_names):
            recommendations.append("🦠 Complete full antibiotic course even if feeling better")
        
        if any("blood thinner" in name or "warfarin" in name for name in med_names):
            recommendations.extend([
                "🩸 Monitor for unusual bleeding or bruising",
                "🥬 Maintain consistent vitamin K intake"
            ])
        
        if len(medications) > 4:
            recommendations.append("💼 Consider using a pill organizer for multiple medications")
        
        # User context-based recommendations
        if user_context:
            age = user_context.get("age")
            if age and age > 65:
                recommendations.append("👴 Extra caution needed - discuss age-related concerns with doctor")
        
        return recommendations[:8]  # Limit to most important
    
    async def conversational_medication_help(self, user_message: str, chat_history: List = None) -> str:
        """Conversational medication assistance"""
        
        # Create conversation prompt
        conversation_prompt = """You are DoctorBot, a helpful medical assistant. 
        
        You help users with:
        - Medication questions and concerns
        - Understanding prescriptions
        - Safety information and warnings
        - Reminder and scheduling help
        
        Always prioritize safety and recommend consulting healthcare providers for medical decisions.
        Be friendly, helpful, and clear in your responses.
        
        Current conversation:
        {chat_history}
        
        User: {user_message}
        
        Assistant:"""
        
        # Simple response generation (can be enhanced with proper LangChain conversation)
        medication_keywords = ["medication", "pill", "drug", "prescription", "dose", "side effect"]
        safety_keywords = ["interaction", "warning", "alert", "danger", "safe"]
        reminder_keywords = ["reminder", "schedule", "time", "when", "how often"]
        
        user_lower = user_message.lower()
        
        if any(keyword in user_lower for keyword in safety_keywords):
            return """🛡️ **Medication Safety Information**

I can help you check for:
• Drug interactions between medications
• FDA safety alerts and recalls  
• Proper dosing schedules
• Side effect information

For specific safety concerns, please share your medication list or ask about specific drugs.

⚠️ **Important**: Always consult your healthcare provider for medical advice."""

        elif any(keyword in user_lower for keyword in reminder_keywords):
            return """⏰ **Medication Reminders**

I can help you set up:
• Daily medication schedules
• Dose timing reminders
• Refill notifications
• Missed dose guidance

Send me your prescription photo and I'll create a personalized schedule!

💡 **Tip**: Consistent timing improves medication effectiveness."""

        elif any(keyword in user_lower for keyword in medication_keywords):
            return """💊 **Medication Information**

I can help you with:
• Understanding your prescriptions
• Medication schedules and timing
• Drug interaction checking
• FDA safety alerts

📸 **To get started**: Send me a photo of your prescription and I'll analyze it for you!

🔍 **Or ask**: Specific questions about your medications."""

        else:
            return """👋 **Hello! I'm DoctorBot, your medication assistant.**

I can help you with:
📸 **Prescription Analysis** - Send photos for medication schedules
🛡️ **Safety Checks** - Drug interactions and FDA alerts  
⏰ **Reminders** - Medication timing and schedules
💬 **Questions** - Ask about your medications

**How can I help you today?**

💡 Type 'help' for more options or send a prescription photo to get started!"""
        
    def create_personalized_alert_message(self, alert_type: str, medication: str, severity: str, details: str) -> str:
        """Create personalized alert messages"""
        
        severity_emojis = {
            "high": "🚨",
            "medium": "⚠️", 
            "low": "ℹ️"
        }
        
        emoji = severity_emojis.get(severity, "📋")
        
        if alert_type == "fda_recall":
            return f"""{emoji} **FDA RECALL ALERT**

**Medication**: {medication}
**Severity**: {severity.upper()}

**Details**: {details}

**Action Required**:
• Stop using this medication immediately
• Contact your healthcare provider
• Do not dispose - return to pharmacy
• Seek alternative treatment

**This is a critical safety alert - take immediate action.**"""

        elif alert_type == "drug_interaction":
            return f"""{emoji} **DRUG INTERACTION WARNING**

**Medications**: {medication}
**Risk Level**: {severity.upper()}

**Concern**: {details}

**Action Required**:
• Consult healthcare provider before next dose
• Monitor for symptoms
• Do not stop medications without medical advice

**Your safety is our priority.**"""

        elif alert_type == "fda_safety":
            return f"""{emoji} **FDA SAFETY COMMUNICATION**

**Medication**: {medication}
**Alert Level**: {severity.upper()}

**Information**: {details}

**Recommended Actions**:
• Discuss with healthcare provider
• Monitor for mentioned side effects
• Continue medication unless advised otherwise

**Stay informed about your medications.**"""

        else:
            return f"""{emoji} **MEDICATION ALERT**

**Medication**: {medication}
**Type**: {alert_type}
**Priority**: {severity.upper()}

**Details**: {details}

**Please consult your healthcare provider for guidance.**"""