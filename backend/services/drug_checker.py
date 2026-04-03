import httpx
import asyncio
from typing import List, Dict
from ..models import Medication, DrugWarning
from .fda_service import FDAService
from .notification_service import NotificationService

class DrugInteractionChecker:
    def __init__(self):
        self.openfda_base_url = "https://api.fda.gov/drug"
        self.fda_service = FDAService()
        self.notification_service = NotificationService()
        
        # Enhanced drug interactions database
        self.interaction_db = {
            "warfarin": {
                "interacts_with": ["aspirin", "ibuprofen", "naproxen", "amiodarone"],
                "severity": "high",
                "warning": "Increased risk of bleeding when combined with blood thinners",
                "mechanism": "Enhanced anticoagulation effect"
            },
            "metformin": {
                "interacts_with": ["alcohol", "contrast dye", "furosemide"],
                "severity": "medium", 
                "warning": "May cause lactic acidosis in certain conditions",
                "mechanism": "Impaired lactate clearance"
            },
            "simvastatin": {
                "interacts_with": ["grapefruit", "clarithromycin", "erythromycin", "amiodarone"],
                "severity": "high",
                "warning": "Increased risk of muscle damage and liver problems",
                "mechanism": "CYP3A4 inhibition increases statin levels"
            },
            "digoxin": {
                "interacts_with": ["amiodarone", "verapamil", "quinidine", "clarithromycin"],
                "severity": "high",
                "warning": "May cause dangerous heart rhythm changes",
                "mechanism": "Increased digoxin levels"
            },
            "lithium": {
                "interacts_with": ["ibuprofen", "naproxen", "diclofenac", "lisinopril"],
                "severity": "high",
                "warning": "NSAIDs and ACE inhibitors can increase lithium levels causing toxicity",
                "mechanism": "Reduced renal clearance"
            }
        }
    
    async def comprehensive_safety_check(self, medications: List[Medication]) -> Dict:
        """Comprehensive safety check including FDA data and interactions"""
        results = {
            "interaction_warnings": [],
            "fda_alerts": [],
            "categorized_notifications": {},
            "safety_score": 0,
            "recommendations": []
        }
        
        try:
            # Get basic drug interactions
            interaction_warnings = await self.check_interactions(medications)
            results["interaction_warnings"] = interaction_warnings
            
            # Get comprehensive FDA data
            fda_data = await self.fda_service.get_comprehensive_drug_info(medications)
            fda_warnings = self.fda_service.format_fda_alerts(fda_data)
            results["fda_alerts"] = fda_warnings
            
            # Categorize notifications
            categorized = self.notification_service.categorize_alerts(fda_data, medications)
            results["categorized_notifications"] = categorized
            
            # Calculate safety score
            results["safety_score"] = self._calculate_safety_score(
                interaction_warnings, fda_warnings, medications
            )
            
            # Generate recommendations
            results["recommendations"] = self._generate_safety_recommendations(
                interaction_warnings, fda_warnings, medications
            )
            
        except Exception as e:
            print(f"⚠️ Error in comprehensive safety check: {str(e)}")
            # Fallback to basic interaction check
            results["interaction_warnings"] = await self.check_interactions(medications)
        
        return results
    
    async def check_interactions(self, medications: List[Medication]) -> List[DrugWarning]:
        """Enhanced drug interaction checking"""
        warnings = []
        
        # Extract medication names for comparison
        med_names = [self._normalize_drug_name(med.name) for med in medications]
        
        # Check each medication against others
        for i, med1 in enumerate(medications):
            drug1 = self._normalize_drug_name(med1.name)
            
            # Check against interaction database
            if drug1 in self.interaction_db:
                interaction_info = self.interaction_db[drug1]
                
                # Check if any other prescribed medication interacts
                for j, med2 in enumerate(medications):
                    if i != j:  # Don't compare with itself
                        drug2 = self._normalize_drug_name(med2.name)
                        
                        if drug2 in interaction_info["interacts_with"]:
                            warning = DrugWarning(
                                severity=interaction_info["severity"],
                                message=f"⚠️ INTERACTION: {interaction_info['warning']} ({med1.name} + {med2.name})\n💡 Mechanism: {interaction_info.get('mechanism', 'Unknown')}",
                                affected_medications=[med1.name, med2.name]
                            )
                            warnings.append(warning)
        
        # Check for duplicate medications
        duplicate_warnings = self._check_duplicates(medications)
        warnings.extend(duplicate_warnings)
        
        # Check for age-related concerns
        age_warnings = self._check_age_related_concerns(medications)
        warnings.extend(age_warnings)
        
        # Remove duplicate warnings
        unique_warnings = self._remove_duplicate_warnings(warnings)
        
        return unique_warnings
    
    def _check_age_related_concerns(self, medications: List[Medication]) -> List[DrugWarning]:
        """Check for age-related medication concerns"""
        warnings = []
        
        # Beers Criteria - potentially inappropriate medications for elderly
        elderly_concerns = {
            "diazepam": "Increased fall risk in elderly patients",
            "diphenhydramine": "Anticholinergic effects, confusion risk",
            "amitriptyline": "Anticholinergic and sedating effects",
            "indomethacin": "CNS adverse effects"
        }
        
        for med in medications:
            normalized_name = self._normalize_drug_name(med.name)
            
            if normalized_name in elderly_concerns:
                warning = DrugWarning(
                    severity="medium",
                    message=f"⚠️ AGE CONCERN: {elderly_concerns[normalized_name]} (Consider alternatives for patients >65)",
                    affected_medications=[med.name]
                )
                warnings.append(warning)
        
        return warnings
    
    def _calculate_safety_score(self, interactions: List[DrugWarning], fda_alerts: List[DrugWarning], medications: List[Medication]) -> int:
        """Calculate overall safety score (0-100, higher is safer)"""
        base_score = 100
        
        # Deduct points for interactions
        for warning in interactions:
            if warning.severity == "high":
                base_score -= 20
            elif warning.severity == "medium":
                base_score -= 10
            else:
                base_score -= 5
        
        # Deduct points for FDA alerts
        for alert in fda_alerts:
            if alert.severity == "high":
                base_score -= 15
            elif alert.severity == "medium":
                base_score -= 8
            else:
                base_score -= 3
        
        # Deduct points for polypharmacy (multiple medications)
        if len(medications) > 5:
            base_score -= (len(medications) - 5) * 2
        
        return max(0, min(100, base_score))
    
    def _generate_safety_recommendations(self, interactions: List[DrugWarning], fda_alerts: List[DrugWarning], medications: List[Medication]) -> List[str]:
        """Generate personalized safety recommendations"""
        recommendations = []
        
        # Basic safety recommendations
        recommendations.extend([
            "📋 Keep an updated medication list with you at all times",
            "💊 Take medications exactly as prescribed",
            "🏥 Inform all healthcare providers about all medications you're taking",
            "⏰ Use pill organizers or apps to track medication schedules"
        ])
        
        # Interaction-specific recommendations
        high_severity_interactions = [w for w in interactions if w.severity == "high"]
        if high_severity_interactions:
            recommendations.extend([
                "🚨 URGENT: Contact your healthcare provider about high-risk drug interactions",
                "📞 Consider scheduling an immediate medication review appointment",
                "⚠️ Do not stop medications without consulting your doctor"
            ])
        
        # FDA alert-specific recommendations
        high_severity_alerts = [a for a in fda_alerts if a.severity == "high"]
        if high_severity_alerts:
            recommendations.extend([
                "🔔 Review recent FDA safety alerts with your healthcare provider",
                "📋 Ask about alternative medications if safety concerns exist"
            ])
        
        # Polypharmacy recommendations
        if len(medications) > 5:
            recommendations.extend([
                "💼 Consider a comprehensive medication review with a pharmacist",
                "📝 Ask about medication consolidation opportunities",
                "🔍 Regular monitoring may be needed for multiple medications"
            ])
        
        return recommendations[:8]  # Limit to most important recommendations
    
    def _normalize_drug_name(self, drug_name: str) -> str:
        """Enhanced drug name normalization"""
        normalized = drug_name.lower().strip()
        
        # Remove common suffixes
        suffixes_to_remove = [' tablet', ' capsule', ' mg', ' ml', ' syrup', ' suspension', ' er', ' xl', ' sr']
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        # Handle common brand name mappings
        brand_to_generic = {
            'tylenol': 'acetaminophen',
            'advil': 'ibuprofen',
            'motrin': 'ibuprofen',
            'aleve': 'naproxen',
            'aspirin': 'acetylsalicylic acid',
            'coumadin': 'warfarin',
            'glucophage': 'metformin',
            'zocor': 'simvastatin',
            'lanoxin': 'digoxin'
        }
        
        return brand_to_generic.get(normalized, normalized)
    
    def _check_duplicates(self, medications: List[Medication]) -> List[DrugWarning]:
        """Enhanced duplicate medication checking"""
        warnings = []
        seen_drugs = {}
        
        for med in medications:
            normalized_name = self._normalize_drug_name(med.name)
            
            if normalized_name in seen_drugs:
                warning = DrugWarning(
                    severity="medium",
                    message=f"⚠️ DUPLICATE: Possible duplicate medication detected - {med.name} and {seen_drugs[normalized_name]}. This may lead to overdose.",
                    affected_medications=[med.name, seen_drugs[normalized_name]]
                )
                warnings.append(warning)
            else:
                seen_drugs[normalized_name] = med.name
        
        return warnings
    
    def _remove_duplicate_warnings(self, warnings: List[DrugWarning]) -> List[DrugWarning]:
        """Remove duplicate warnings"""
        unique_warnings = []
        seen_messages = set()
        
        for warning in warnings:
            if warning.message not in seen_messages:
                unique_warnings.append(warning)
                seen_messages.add(warning.message)
        
        return unique_warnings
    
    def get_enhanced_safety_tips(self, medications: List[Medication], safety_score: int) -> List[str]:
        """Get enhanced safety tips based on medications and safety score"""
        tips = [
            "💊 Take medications exactly as prescribed by your doctor",
            "📋 Keep an updated list of all medications, including over-the-counter drugs",
            "🏥 Inform all healthcare providers about all medications you're taking",
            "💧 Store medications in a cool, dry place away from children",
            "📅 Check expiration dates regularly and dispose of expired medications safely"
        ]
        
        # Add safety score specific tips
        if safety_score < 70:
            tips.extend([
                "🚨 Your medication combination has safety concerns - schedule a medication review",
                "📞 Consider consulting with a clinical pharmacist",
                "⚠️ Be extra vigilant for side effects and drug interactions"
            ])
        elif safety_score < 85:
            tips.extend([
                "⚠️ Monitor for potential side effects and interactions",
                "📋 Regular check-ups are important with your current medications"
            ])
        
        # Add medication-specific tips
        med_names = [med.name.lower() for med in medications]
        
        if any('antibiotic' in name or 'amoxicillin' in name for name in med_names):
            tips.append("🦠 Complete the full course of antibiotics even if you feel better")
        
        if any('blood thinner' in name or 'warfarin' in name for name in med_names):
            tips.extend([
                "🩸 Avoid activities that may cause bleeding or injury",
                "🥬 Maintain consistent vitamin K intake (green leafy vegetables)"
            ])
        
        if any('diabetes' in name or 'metformin' in name for name in med_names):
            tips.append("🍽️ Take diabetes medications with meals as directed")
        
        return tips[:10]  # Limit to most relevant tips