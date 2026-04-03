import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
import json
from ..models import Medication, DrugWarning

class NotificationService:
    def __init__(self):
        self.notification_types = {
            "immediate": {
                "triggers": ["high_severity_recall", "black_box_warning", "contraindication"],
                "delivery": "instant"
            },
            "daily": {
                "triggers": ["medium_severity_recall", "adverse_event_spike", "new_warning"],
                "delivery": "daily_digest"
            },
            "weekly": {
                "triggers": ["low_severity_recall", "label_update", "general_advisory"],
                "delivery": "weekly_summary"
            }
        }
    
    def categorize_alerts(self, fda_data: Dict, medications: List[Medication]) -> Dict:
        """Categorize FDA alerts by notification type and urgency"""
        categorized = {
            "critical_immediate": [],
            "important_daily": [],
            "informational_weekly": [],
            "medication_specific": {},
            "general_advisories": []
        }
        
        # Process each medication
        for medication in medications:
            med_name = medication.name
            categorized["medication_specific"][med_name] = {
                "critical": [],
                "warnings": [],
                "updates": []
            }
        
        # Categorize recalls
        for recall in fda_data.get("recalls", []):
            alert = self._create_recall_alert(recall)
            
            if recall["severity"] == "high":
                categorized["critical_immediate"].append(alert)
            elif recall["severity"] == "medium":
                categorized["important_daily"].append(alert)
            else:
                categorized["informational_weekly"].append(alert)
        
        # Categorize safety alerts
        for safety_alert in fda_data.get("safety_alerts", []):
            alert = self._create_safety_alert(safety_alert)
            
            if safety_alert["severity"] == "high":
                categorized["critical_immediate"].append(alert)
            else:
                categorized["important_daily"].append(alert)
        
        # Categorize adverse events
        for event in fda_data.get("adverse_events", []):
            if event["count"] > 2000:  # Significant spike
                alert = self._create_adverse_event_alert(event)
                categorized["important_daily"].append(alert)
        
        # Categorize label warnings
        for warning in fda_data.get("label_warnings", []):
            alert = self._create_label_warning_alert(warning)
            
            if warning["severity"] == "high":
                categorized["critical_immediate"].append(alert)
            elif warning["severity"] == "medium":
                categorized["important_daily"].append(alert)
            else:
                categorized["informational_weekly"].append(alert)
        
        return categorized
    
    def _create_recall_alert(self, recall: Dict) -> Dict:
        """Create structured recall alert"""
        return {
            "type": "recall",
            "severity": recall["severity"],
            "title": f"FDA Drug Recall - Class {recall.get('classification', 'Unknown')}",
            "message": recall["reason"],
            "product": recall["product"],
            "company": recall["company"],
            "date": recall["date"],
            "action_required": self._get_recall_action(recall["severity"]),
            "icon": "🚨" if recall["severity"] == "high" else "⚠️"
        }
    
    def _create_safety_alert(self, alert: Dict) -> Dict:
        """Create structured safety alert"""
        return {
            "type": "safety_alert",
            "severity": alert["severity"],
            "title": "FDA Safety Communication",
            "message": alert["message"],
            "source": alert.get("source", "FDA"),
            "date": alert.get("date", datetime.now().strftime("%Y-%m-%d")),
            "action_required": "Review with healthcare provider",
            "icon": "🔔"
        }
    
    def _create_adverse_event_alert(self, event: Dict) -> Dict:
        """Create adverse event alert"""
        return {
            "type": "adverse_event",
            "severity": event["severity"],
            "title": "Adverse Event Report",
            "message": f"Increased reports of {event['reaction']} ({event['count']} cases)",
            "reaction": event["reaction"],
            "count": event["count"],
            "action_required": "Monitor for symptoms",
            "icon": "📊"
        }
    
    def _create_label_warning_alert(self, warning: Dict) -> Dict:
        """Create label warning alert"""
        return {
            "type": "label_warning",
            "severity": warning["severity"],
            "title": f"Drug Label {warning['section']}",
            "message": warning["text"][:200] + "..." if len(warning["text"]) > 200 else warning["text"],
            "section": warning["section"],
            "action_required": "Read full prescribing information",
            "icon": "📋"
        }
    
    def _get_recall_action(self, severity: str) -> str:
        """Get recommended action for recall severity"""
        actions = {
            "high": "STOP using immediately and contact healthcare provider",
            "medium": "Contact healthcare provider before next dose",
            "low": "Discuss with healthcare provider at next appointment"
        }
        return actions.get(severity, "Contact healthcare provider")
    
    def format_immediate_notifications(self, alerts: List[Dict]) -> List[str]:
        """Format critical alerts for immediate notification"""
        notifications = []
        
        for alert in alerts:
            notification = f"{alert['icon']} **URGENT: {alert['title']}**\n\n"
            notification += f"📋 **Issue**: {alert['message']}\n"
            notification += f"🎯 **Action**: {alert['action_required']}\n"
            
            if alert.get('product'):
                notification += f"💊 **Product**: {alert['product']}\n"
            
            if alert.get('date'):
                notification += f"📅 **Date**: {alert['date']}\n"
            
            notification += "\n⚠️ **This is a critical safety alert. Please take immediate action.**"
            notifications.append(notification)
        
        return notifications
    
    def format_daily_digest(self, alerts: List[Dict]) -> str:
        """Format daily digest of important alerts"""
        if not alerts:
            return None
        
        digest = "📬 **Daily FDA Safety Digest**\n\n"
        digest += f"📅 {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        # Group by type
        by_type = {}
        for alert in alerts:
            alert_type = alert['type']
            if alert_type not in by_type:
                by_type[alert_type] = []
            by_type[alert_type].append(alert)
        
        for alert_type, type_alerts in by_type.items():
            digest += f"## {alert_type.replace('_', ' ').title()}s\n\n"
            
            for alert in type_alerts:
                digest += f"{alert['icon']} **{alert['title']}**\n"
                digest += f"   {alert['message'][:150]}...\n"
                digest += f"   *Action: {alert['action_required']}*\n\n"
        
        digest += "---\n"
        digest += "💡 **Tip**: Always consult your healthcare provider before making medication changes.\n"
        digest += "🔔 You can adjust notification preferences in settings."
        
        return digest
    
    def format_weekly_summary(self, alerts: List[Dict]) -> str:
        """Format weekly summary of informational alerts"""
        if not alerts:
            return None
        
        summary = "📊 **Weekly FDA Safety Summary**\n\n"
        summary += f"📅 Week of {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        summary += f"📈 **This Week's Updates**: {len(alerts)} new items\n\n"
        
        # Categorize by importance
        high_priority = [a for a in alerts if a['severity'] == 'medium']
        low_priority = [a for a in alerts if a['severity'] == 'low']
        
        if high_priority:
            summary += "### 🔶 Important Updates\n\n"
            for alert in high_priority[:5]:  # Top 5
                summary += f"• {alert['title']}: {alert['message'][:100]}...\n"
            summary += "\n"
        
        if low_priority:
            summary += "### 📋 General Information\n\n"
            summary += f"• {len(low_priority)} general advisories and label updates\n"
            summary += "• No immediate action required\n\n"
        
        summary += "---\n"
        summary += "📱 For detailed information, check the FDA Safety Dashboard in the app."
        
        return summary
    
    def create_medication_specific_alerts(self, categorized_alerts: Dict, medications: List[Medication]) -> Dict:
        """Create personalized alerts for each medication"""
        personalized = {}
        
        for medication in medications:
            med_name = medication.name
            med_alerts = []
            
            # Check all alert categories for this medication
            all_alerts = (
                categorized_alerts.get("critical_immediate", []) +
                categorized_alerts.get("important_daily", []) +
                categorized_alerts.get("informational_weekly", [])
            )
            
            for alert in all_alerts:
                # Check if alert is relevant to this medication
                if self._is_alert_relevant(alert, medication):
                    personalized_alert = {
                        **alert,
                        "medication": med_name,
                        "dosage": medication.dosage,
                        "frequency": medication.frequency,
                        "personalized_message": self._personalize_alert_message(alert, medication)
                    }
                    med_alerts.append(personalized_alert)
            
            if med_alerts:
                personalized[med_name] = med_alerts
        
        return personalized
    
    def _is_alert_relevant(self, alert: Dict, medication: Medication) -> bool:
        """Check if an alert is relevant to a specific medication"""
        med_name_lower = medication.name.lower()
        
        # Check if medication name appears in alert
        alert_text = (
            alert.get('message', '') + ' ' +
            alert.get('product', '') + ' ' +
            alert.get('title', '')
        ).lower()
        
        # Simple relevance check - can be enhanced with drug name databases
        return any(word in alert_text for word in med_name_lower.split())
    
    def _personalize_alert_message(self, alert: Dict, medication: Medication) -> str:
        """Create personalized alert message for specific medication"""
        base_message = alert['message']
        
        personalized = f"**Your medication: {medication.name} ({medication.dosage})**\n\n"
        personalized += f"{alert['icon']} {base_message}\n\n"
        personalized += f"📋 **Your current schedule**: {medication.frequency}\n"
        personalized += f"🎯 **Recommended action**: {alert['action_required']}\n\n"
        personalized += "💡 **Next steps**: Discuss this alert with your healthcare provider at your next appointment."
        
        return personalized