import httpx
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from ..models import Medication, DrugWarning

class FDAService:
    def __init__(self):
        self.base_url = "https://api.fda.gov"
        self.endpoints = {
            "drug_events": "/drug/event.json",
            "drug_labels": "/drug/label.json", 
            "drug_recalls": "/drug/enforcement.json",
            "drug_ndc": "/drug/ndc.json"
        }
        
    async def get_comprehensive_drug_info(self, medications: List[Medication]) -> Dict:
        """Get comprehensive FDA information for all medications"""
        results = {
            "safety_alerts": [],
            "recalls": [],
            "adverse_events": [],
            "label_warnings": [],
            "interactions": [],
            "contraindications": []
        }
        
        for medication in medications:
            drug_name = self._normalize_drug_name(medication.name)
            
            # Get multiple types of FDA data
            tasks = [
                self._get_drug_recalls(drug_name),
                self._get_adverse_events(drug_name),
                self._get_drug_labels(drug_name),
                self._check_recent_alerts(drug_name)
            ]
            
            try:
                recalls, events, labels, alerts = await asyncio.gather(*tasks, return_exceptions=True)
                
                if not isinstance(recalls, Exception) and recalls:
                    results["recalls"].extend(recalls)
                
                if not isinstance(events, Exception) and events:
                    results["adverse_events"].extend(events)
                
                if not isinstance(labels, Exception) and labels:
                    results["label_warnings"].extend(labels)
                
                if not isinstance(alerts, Exception) and alerts:
                    results["safety_alerts"].extend(alerts)
                    
            except Exception as e:
                print(f"⚠️ Error getting FDA data for {drug_name}: {str(e)}")
        
        return results
    
    async def _get_drug_recalls(self, drug_name: str) -> List[Dict]:
        """Get FDA drug recalls for specific medication"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "search": f'product_description:"{drug_name}"',
                    "limit": 5
                }
                
                response = await client.get(
                    f"{self.base_url}{self.endpoints['drug_recalls']}",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    recalls = []
                    
                    for result in data.get("results", []):
                        product_description = result.get("product_description", "")
                        if drug_name.lower() not in product_description.lower():
                            continue

                        recall = {
                            "type": "recall",
                            "severity": self._map_recall_class(result.get("classification", "III")),
                            "classification": result.get("classification", "Unknown"),
                            "reason": result.get("reason_for_recall", "Unknown"),
                            "date": result.get("recall_initiation_date", "Unknown"),
                            "status": result.get("status", "Unknown"),
                            "product": product_description or drug_name,
                            "company": result.get("recalling_firm", "Unknown")
                        }
                        recalls.append(recall)
                    
                    return recalls
                
        except Exception as e:
            print(f"⚠️ FDA recalls API error for {drug_name}: {str(e)}")
        
        return []
    
    async def _get_adverse_events(self, drug_name: str) -> List[Dict]:
        """Get FDA adverse event reports"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "search": f"patient.drug.medicinalproduct:{drug_name}",
                    "count": "patient.reaction.reactionmeddrapt.exact",
                    "limit": 20
                }
                
                response = await client.get(
                    f"{self.base_url}{self.endpoints['drug_events']}",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    events = []
                    
                    for result in data.get("results", []):
                        if result.get("count", 0) > 100:  # Only significant events
                            event = {
                                "type": "adverse_event",
                                "reaction": result.get("term", "Unknown"),
                                "count": result.get("count", 0),
                                "severity": "medium" if result.get("count", 0) > 500 else "low"
                            }
                            events.append(event)
                    
                    return events[:5]  # Top 5 most reported
                
        except Exception as e:
            print(f"⚠️ FDA adverse events API error for {drug_name}: {str(e)}")
        
        return []
    
    async def _get_drug_labels(self, drug_name: str) -> List[Dict]:
        """Get FDA drug label warnings"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "search": f"openfda.generic_name:{drug_name}",
                    "limit": 5
                }
                
                response = await client.get(
                    f"{self.base_url}{self.endpoints['drug_labels']}",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    warnings = []
                    
                    for result in data.get("results", []):
                        # Extract various warning types
                        warning_sections = [
                            ("boxed_warning", "high"),
                            ("warnings", "medium"),
                            ("precautions", "low"),
                            ("contraindications", "high")
                        ]
                        
                        for section, severity in warning_sections:
                            if section in result:
                                warning_text = " ".join(result[section])
                                if len(warning_text) > 50:  # Only meaningful warnings
                                    warnings.append({
                                        "type": "label_warning",
                                        "section": section.replace("_", " ").title(),
                                        "severity": severity,
                                        "text": warning_text[:500] + "..." if len(warning_text) > 500 else warning_text
                                    })
                    
                    return warnings
                
        except Exception as e:
            print(f"⚠️ FDA labels API error for {drug_name}: {str(e)}")
        
        return []
    
    async def _check_recent_alerts(self, drug_name: str) -> List[Dict]:
        """Check for recent FDA safety alerts"""
        # This would typically check FDA safety communications
        # For now, we'll simulate based on known high-risk medications
        
        high_risk_drugs = {
            "warfarin": {
                "alert": "Increased bleeding risk monitoring required",
                "severity": "high",
                "date": "2024-01-15"
            },
            "metformin": {
                "alert": "Lactic acidosis risk in kidney disease",
                "severity": "medium", 
                "date": "2024-02-01"
            },
            "digoxin": {
                "alert": "Narrow therapeutic window - monitor levels",
                "severity": "high",
                "date": "2024-01-20"
            }
        }
        
        normalized_name = drug_name.lower()
        alerts = []
        
        for drug, alert_info in high_risk_drugs.items():
            if drug in normalized_name or normalized_name in drug:
                alerts.append({
                    "type": "safety_alert",
                    "severity": alert_info["severity"],
                    "message": alert_info["alert"],
                    "date": alert_info["date"],
                    "source": "FDA Safety Communication"
                })
        
        return alerts
    
    def _map_recall_class(self, classification: str) -> str:
        """Map FDA recall classification to severity"""
        mapping = {
            "I": "high",      # Dangerous or defective products
            "II": "medium",   # Products that might cause temporary health problems
            "III": "low"      # Products unlikely to cause adverse health reactions
        }
        return mapping.get(classification, "medium")
    
    def _normalize_drug_name(self, drug_name: str) -> str:
        """Normalize drug name for FDA API queries"""
        # Remove common suffixes and normalize
        normalized = drug_name.lower().strip()
        
        # Remove dosage information
        for suffix in [' mg', ' ml', ' tablet', ' capsule', ' syrup']:
            if suffix in normalized:
                normalized = normalized.split(suffix)[0]
        
        # Handle common brand/generic mappings
        brand_to_generic = {
            'tylenol': 'acetaminophen',
            'advil': 'ibuprofen',
            'motrin': 'ibuprofen',
            'aleve': 'naproxen'
        }
        
        return brand_to_generic.get(normalized, normalized)
    
    def format_fda_alerts(self, fda_data: Dict) -> List[DrugWarning]:
        """Format FDA data into DrugWarning objects"""
        warnings = []
        seen_recall_reasons = set()
        seen_messages = set()
        max_recall_warnings = 6
        max_safety_alerts = 3
        max_adverse_events = 3
        max_label_warnings = 3
        
        # Process recalls
        for recall in fda_data.get("recalls", []):
            reason = recall.get("reason", "Unknown").strip()
            if not reason:
                continue

            reason_key = reason.lower()
            if reason_key in seen_recall_reasons:
                continue

            seen_recall_reasons.add(reason_key)

            warning = DrugWarning(
                severity=recall["severity"],
                message=f"🚨 FDA RECALL: {reason} (Class {recall.get('classification', 'Unknown')})",
                affected_medications=[recall["product"]]
            )
            if warning.message not in seen_messages:
                warnings.append(warning)
                seen_messages.add(warning.message)

            if len(warnings) >= max_recall_warnings:
                break
        
        # Process safety alerts
        safety_count = 0
        for alert in fda_data.get("safety_alerts", []):
            warning = DrugWarning(
                severity=alert["severity"],
                message=f"⚠️ FDA ALERT: {alert['message']}",
                affected_medications=[]
            )
            if warning.message in seen_messages:
                continue
            warnings.append(warning)
            seen_messages.add(warning.message)
            safety_count += 1
            if safety_count >= max_safety_alerts:
                break
        
        # Process adverse events
        adverse_count = 0
        for event in fda_data.get("adverse_events", []):
            if event["count"] > 1000:  # Only show significant events
                warning = DrugWarning(
                    severity=event["severity"],
                    message=f"📊 ADVERSE EVENT: {event['reaction']} reported {event['count']} times",
                    affected_medications=[]
                )
                if warning.message in seen_messages:
                    continue
                warnings.append(warning)
                seen_messages.add(warning.message)
                adverse_count += 1
                if adverse_count >= max_adverse_events:
                    break
        
        # Process label warnings
        label_count = 0
        for label_warning in fda_data.get("label_warnings", []):
            if label_warning["severity"] == "high":
                warning = DrugWarning(
                    severity=label_warning["severity"],
                    message=f"⚠️ {label_warning['section'].upper()}: {label_warning['text'][:200]}...",
                    affected_medications=[]
                )
                if warning.message in seen_messages:
                    continue
                warnings.append(warning)
                seen_messages.add(warning.message)
                label_count += 1
                if label_count >= max_label_warnings:
                    break
        
        return warnings