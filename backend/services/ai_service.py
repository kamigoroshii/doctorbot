import os
import httpx
import json
import re
import io
import base64
import asyncio
from difflib import get_close_matches
from typing import List
from dotenv import load_dotenv
from PIL import Image
from ..models import Medication, MedicationSchedule

# Load environment variables
load_dotenv()

class AIService:
    KNOWN_DRUG_NAMES = [
        # Common generics
        "amoxicillin", "ibuprofen", "omeprazole", "cetirizine", "vitamin d3",
        "paracetamol", "acetaminophen", "aspirin", "metformin", "lisinopril",
        "glimepiride", "amlodipine", "atorvastatin", "simvastatin", "pantoprazole",
        "metoprolol", "losartan", "gabapentin", "sertraline", "fluoxetine",
        "azithromycin", "ciprofloxacin", "doxycycline", "prednisone", "albuterol",
        "insulin", "levothyroxine", "warfarin", "clopidogrel", "diclofenac",
        "naproxen", "tramadol", "codeine", "morphine", "hydrocodone",
        "clonazepam", "lorazepam", "alprazolam", "diazepam", "zolpidem",
        "esomeprazole", "ranitidine", "famotidine", "ondansetron", "promethazine",
        "furosemide", "hydrochlorothiazide", "spironolactone", "potassium",
        "folic acid", "vitamin b12", "vitamin c", "calcium", "iron", "magnesium",
        "multivitamin", "fish oil", "omega-3", "probiotics", "melatonin",
        # Antibiotics
        "ampicillin", "cloxacillin", "cephalexin", "cefuroxime", "cefixime",
        "ceftriaxone", "metronidazole", "tinidazole", "clarithromycin",
        "erythromycin", "tetracycline", "levofloxacin", "ofloxacin", "norfloxacin",
        "nitrofurantoin", "cotrimoxazole", "trimethoprim", "amikacin", "gentamicin",
        "clindamycin", "linezolid", "vancomycin", "meropenem", "piperacillin",
        # Cardiac / antihypertensive
        "ramipril", "enalapril", "telmisartan", "olmesartan", "valsartan",
        "irbesartan", "carvedilol", "bisoprolol", "nebivolol", "atenolol",
        "nifedipine", "diltiazem", "verapamil", "digoxin", "amiodarone",
        "isosorbide", "nitroglycerin", "rosuvastatin", "fenofibrate", "ezetimibe",
        # Diabetes
        "glibenclamide", "gliclazide", "glipizide", "pioglitazone", "sitagliptin",
        "vildagliptin", "dapagliflozin", "empagliflozin", "acarbose", "repaglinide",
        # GI / antacids
        "rabeprazole", "lansoprazole", "domperidone", "metoclopramide",
        "dicyclomine", "hyoscine", "loperamide", "sucralfate", "antacid",
        "lactulose", "bisacodyl", "senna", "activated charcoal",
        # Pain / anti-inflammatory
        "aceclofenac", "ketorolac", "piroxicam", "meloxicam", "celecoxib",
        "etoricoxib", "mefenamic acid", "nimesulide", "pregabalin",
        "baclofen", "tizanidine", "methocarbamol", "thiocolchicoside",
        # Respiratory
        "salbutamol", "terbutaline", "ipratropium", "tiotropium", "salmeterol",
        "formoterol", "budesonide", "fluticasone", "beclomethasone", "montelukast",
        "levocetirizine", "fexofenadine", "loratadine", "desloratadine",
        "dextromethorphan", "bromhexine", "ambroxol", "guaifenesin",
        # CNS / Psych
        "escitalopram", "paroxetine", "venlafaxine", "duloxetine", "mirtazapine",
        "bupropion", "quetiapine", "olanzapine", "risperidone", "haloperidol",
        "phenobarbitone", "phenytoin", "carbamazepine", "valproate", "lamotrigine",
        "levetiracetam", "topiramate", "donepezil", "memantine",
        # Vitamins / supplements
        "vitamin d", "vitamin a", "vitamin e", "vitamin k", "zinc",
        "selenium", "chromium", "biotin", "coenzyme q10", "b complex",
        "dha", "epa", "glucosamine", "chondroitin",
        # Common Indian brand names (OCR often captures brand instead of generic)
        "crocin", "dolo", "combiflam", "brufen", "meftal", "voveran",
        "pan", "pantocid", "omez", "nexpro", "nexium", "zantac",
        "augmentin", "clavam", "zithromax", "azee", "cifran", "ciplox",
        "taxim", "monocef", "sporidex", "rantac", "digene", "gelusil",
        "glycomet", "glucobay", "januvia", "jardiance", "galvus",
        "telma", "losar", "amlovas", "stamlo", "concor", "betaloc",
        "ramistar", "cardace", "covance", "repace", "aprovel",
        "crestor", "rozucor", "storvas", "tonact", "fenofibrate",
        "ativan", "rivotril", "alprax", "restyl", "nitrosun",
        "syndopa", "sifrol", "aricept", "glyciphage", "obimet",
        "aristozyme", "unienzyme", "becadexamin", "neurobion",
    ]


    def __init__(self):
        # Support multiple AI providers
        self.provider = os.getenv("AI_PROVIDER", "demo").lower()
        
        if self.provider == "demo":
            # Demo mode - no API key required, uses intelligent regex parsing
            self.api_key = None
            self.base_url = None
            self.model_name = "demo-parser"
            print("🎮 AI Service running in DEMO mode (no API key required)")
        elif self.provider == "grok":
            self.api_key = os.getenv("GROK_API_KEY")
            if not self.api_key or "here" in self.api_key.lower():
                raise ValueError("GROK_API_KEY environment variable is required (not a placeholder)")
            self.base_url = "https://api.x.ai/v1"
            self.model_name = "grok-beta"
        elif self.provider == "openrouter":
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            if not self.api_key or "here" in self.api_key.lower():
                raise ValueError("OPENROUTER_API_KEY environment variable is required (not a placeholder)")
            self.base_url = "https://openrouter.ai/api/v1"
            # Use a good free model available on OpenRouter
            self.model_name = "upstage/solar-pro-3:free"
        elif self.provider == "gemini":
            import google.generativeai as genai
            self.api_key = os.getenv("GOOGLE_API_KEY")
            if not self.api_key or "here" in self.api_key.lower():
                raise ValueError("GOOGLE_API_KEY environment variable is required (not a placeholder)")
            genai.configure(api_key=self.api_key)
            self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            try:
                self.model = genai.GenerativeModel(self.gemini_model_name)
            except Exception:
                # Fallback to a known-good model name if the configured one is invalid
                self.gemini_model_name = "gemini-2.0-flash"
                self.model = genai.GenerativeModel(self.gemini_model_name)
            print(f"✅ Gemini SDK model: {self.gemini_model_name}")
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}. Use: demo, openrouter, grok, or gemini")
        
        # Define the prompt template for prescription parsing
        self.prompt_template = """
Extract medication information from this prescription text and return ONLY valid JSON.

Prescription Text:
{prescription_text}

Return ONLY this JSON structure with actual medication names and details:
{{
    "medications": [
        {{
            "name": "exact medication name (e.g., Amoxicillin, Ibuprofen)",
            "dosage": "dosage with unit (e.g., 500mg, 875mg)",
            "frequency": "frequency in words (e.g., twice daily, three times daily)",
            "times_per_day": number,
            "schedule_times": ["HH:MM", "HH:MM"],
            "instructions": "additional instructions if any"
        }}
    ]
}}

Medical abbreviations:
- BD/BID = twice daily (08:00, 20:00)
- TID = three times daily (08:00, 14:00, 20:00)  
- QID = four times daily (08:00, 12:00, 16:00, 20:00)
- OD = once daily (08:00)
- PRN = as needed

Extract the actual drug names like "Amoxicillin", "Ibuprofen", etc. Do not use generic words like "Take" or "Tablet".
Return only the JSON, no other text.
"""
    
    async def validate_api_key(self) -> dict:
        """Test if the configured AI API key is valid and has available credits"""
        try:
            # Demo mode always works
            if self.provider == "demo":
                return {"status": "ok", "provider": "demo", "credits": "Unlimited (demo mode)"}

            if self.provider == "gemini":
                response = self.model.generate_content("Say OK")
                return {"status": "ok", "provider": "gemini", "credits": "N/A (Gemini quota-based)"}

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            if self.provider == "openrouter":
                headers.update({"HTTP-Referer": "https://doctorbot.local", "X-Title": "DoctorBot"})

            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )

            if response.status_code == 200:
                data = response.json()
                # Try to extract remaining credits/tokens from response headers or body
                credits = "Available"
                if self.provider == "openrouter":
                    # OpenRouter returns usage info
                    usage = data.get("usage", {})
                    credits = f"Used {usage.get('total_tokens', '?')} tokens on test call — key is active"
                return {"status": "ok", "provider": self.provider, "credits": credits}
            elif response.status_code in (401, 403):
                return {"status": "invalid_key", "provider": self.provider, "credits": "N/A", "detail": "API key rejected"}
            elif response.status_code == 429:
                return {"status": "rate_limited", "provider": self.provider, "credits": "Possibly exhausted", "detail": "Rate limit or quota exceeded"}
            else:
                return {"status": "error", "provider": self.provider, "credits": "Unknown", "detail": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"status": "error", "provider": self.provider, "credits": "Unknown", "detail": str(e)}

    async def parse_prescription(self, prescription_text: str) -> MedicationSchedule:
        """Parse prescription text using configured AI provider.
        
        This method NEVER raises — it always returns a MedicationSchedule,
        falling back through demo-mode and regex parsing as needed.
        """
        print(f"📝 OCR text preview (first 500 chars):\n{prescription_text[:500]}")
        try:
            if self.provider == "demo":
                schedule = self._parse_demo_mode(prescription_text)
                if schedule.total_medications == 0:
                    gemini_schedule = await self._try_gemini_fallback(prescription_text)
                    if gemini_schedule:
                        return gemini_schedule
                return schedule
            elif self.provider == "grok":
                return await self._parse_with_grok(prescription_text)
            elif self.provider == "openrouter":
                return await self._parse_with_openrouter(prescription_text)
            elif self.provider == "gemini":
                return await self._parse_with_gemini(prescription_text)
            else:
                print(f"⚠️  Unknown provider '{self.provider}' – using demo mode parser")
                return self._parse_demo_mode(prescription_text)

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON decode error in parse_prescription: {e} – using fallback parser")
            return self._fallback_parsing(prescription_text)
        except Exception as e:
            print(f"⚠️  parse_prescription error ({type(e).__name__}: {e}) – using fallback parser")
            # Last resort: always return something rather than crash the endpoint
            try:
                return self._parse_demo_mode(prescription_text)
            except Exception:
                return MedicationSchedule(medications=[], total_medications=0)

    async def parse_prescription_from_image(self, image_data: bytes) -> MedicationSchedule | None:
        """Parse medications directly from image using Gemini Vision.
        
        Works even when AI_PROVIDER is not 'gemini' – uses the GOOGLE_API_KEY
        as an optional enhancement layer.  This is the primary path for all
        handwritten prescription photos.
        """
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key or "here" in google_key.lower():
            print("⚠️  GOOGLE_API_KEY not configured – skipping Gemini Vision path")
            return None

        try:
            prompt = """You are a medical prescription reader specialising in handwritten doctor prescriptions.

Look carefully at every line in this image. Extract EVERY medication listed.

Common handwriting interpretation rules:
- "Rx" or "R/" at the top marks the start of the prescription
- Drug names are usually the first word on each medicine line (e.g. Amoxicillin, Lisinopril, Metformin)
- Dosage follows the drug name (e.g. 500mg, 10mg, 20mg)
- Instructions follow: "1 cap", "1 tab", "1 tablet"
- Frequency abbreviations: TID=3×/day, BID=2×/day, OD=1×/day, HS=at night, QID=4×/day
- "x 7 days", "x7d" = duration, not frequency
- "with meals", "before breakfast" = instructions
- Slanted / cursive writing is common – read carefully

For EACH medication line found, produce one JSON object.

Return ONLY this exact JSON – NO markdown, NO code fences, NO extra text:
{"medications": [{"name": "ExactDrugName", "dosage": "XXXmg", "frequency": "frequency in plain English", "times_per_day": N, "schedule_times": ["HH:MM"], "instructions": "any extra instructions or null"}]}

Frequency → schedule_times mapping:
- once daily / OD / daily  → ["08:00"]
- twice daily / BID / BD   → ["08:00", "20:00"]
- three times / TID        → ["08:00", "14:00", "20:00"]
- four times / QID         → ["08:00", "12:00", "16:00", "20:00"]
- at night / HS / bedtime  → ["22:00"]

If you cannot read the image at all, return: {"medications": []}
"""

            # Prepare the image – upscale small images for better vision accuracy
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            w, h = image.size
            if max(w, h) < 1200:
                scale = 1200 / max(w, h)
                image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            image_buffer = io.BytesIO()
            image.save(image_buffer, format="JPEG", quality=90)
            image_b64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

            response_text = await asyncio.to_thread(
                self._call_gemini_rest,
                prompt,
                image_b64,
                "image/jpeg"
            )
            if not response_text:
                print("⚠️  Gemini Vision returned no text – trying OpenRouter text fallback")
                # OpenRouter can't process images directly, so we skip to None
                # (the caller will use OCR → text parser pipeline)
                return None

            print(f"🔍 Gemini Vision raw response (first 300 chars): {response_text[:300]}")
            schedule = self._parse_response_to_schedule(response_text)
            if schedule.total_medications > 0:
                print(f"✅ Gemini Vision found {schedule.total_medications} medication(s)")
                return schedule
            print("⚠️  Gemini Vision parsed 0 medications from image")
            return None
        except Exception as exc:
            print(f"⚠️  Gemini Vision error: {exc}")
            return None

    def _parse_demo_mode(self, text: str) -> MedicationSchedule:
        """Intelligent prescription parsing without AI API - for demo/testing"""
        medications = []

        freq_patterns = {
            r'\b(TID|t\.?i\.?d\.?|three times daily|3 times daily|thrice daily)\b': ('three times daily', 3, ['08:00', '14:00', '20:00']),
            r'\b(QID|q\.?i\.?d\.?|four times daily|4 times daily)\b': ('four times daily', 4, ['08:00', '12:00', '16:00', '20:00']),
            r'\b(BD|BID|b\.?i?\.?d\.?|twice daily|2 times daily|two times daily)\b': ('twice daily', 2, ['08:00', '20:00']),
            r'\b(OD|o\.?d\.?|once daily|1 time daily|one time daily|daily|every day)\b': ('once daily', 1, ['08:00']),
            r'\b(at night|nocte|hs|h\.?s\.?|bedtime|before bed)\b': ('once daily at night', 1, ['22:00']),
            r'\b(PRN|p\.?r\.?n\.?|as needed|when needed|if needed)\b': ('as needed', 1, ['08:00']),
        }

        instruction_patterns = [
            r'(take (?:with|after|before) (?:food|meals?|breakfast|lunch|dinner))',
            r'(on empty stomach)',
            r'(may cause drowsiness)',
            r'(avoid (?:alcohol|driving|sun))',
            r'(complete (?:full )?course)',
            r'(do not (?:crush|chew))',
            r'(with meals?)',
            r'(after food)',
            r'(before food)',
            r'(at bedtime)',
        ]

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # ── Pass 1: match against KNOWN_DRUG_NAMES ──────────────────────────
        for index, line in enumerate(lines):
            normalized_line = self._normalize_ocr_compact_text(line)
            if not self._looks_like_medication_line(normalized_line):
                continue
            drug = self._resolve_drug_name(normalized_line)
            if not drug:
                continue

            nearby_lines = [normalized_line]
            if index + 1 < len(lines):
                next_normalized = self._normalize_ocr_compact_text(lines[index + 1])
                if self._is_followup_medication_context(next_normalized):
                    nearby_lines.append(next_normalized)
            if index + 2 < len(lines) and 'instruction' in lines[index + 2].lower():
                nearby_lines.append(self._normalize_ocr_compact_text(lines[index + 2]))

            context_text = ' '.join(nearby_lines)
            dosage, frequency, times_per_day, schedule_times, instructions = \
                self._extract_dosage_freq_instructions(context_text, freq_patterns, instruction_patterns)

            medications.append(Medication(
                name=drug.title(),
                dosage=dosage,
                frequency=frequency,
                times_per_day=times_per_day,
                schedule_times=schedule_times,
                instructions=instructions
            ))

        # ── Pass 2: dosage/frequency signature extractor (noisy OCR) ────────
        backup_medications = self._extract_medications_from_ocr_lines(lines)
        if len(medications) < 2 and backup_medications:
            medications.extend(backup_medications)

        # ── Pass 3: pattern rescue — ANY word + dosage, no name dict needed ──
        # Catches drugs completely absent from KNOWN_DRUG_NAMES list
        if len(medications) == 0:
            medications = self._pattern_rescue(lines, freq_patterns, instruction_patterns)

        if not medications:
            return self._fallback_parsing(text)

        medications = self._deduplicate_medications(medications)
        print(f"🎮 Demo parser found {len(medications)} medication(s)")
        return MedicationSchedule(medications=medications, total_medications=len(medications))

    def _extract_dosage_freq_instructions(self, context_text: str, freq_patterns: dict, instruction_patterns: list):
        """Helper: extract dosage, frequency, and instructions from a context string."""
        dosage_match = re.search(
            r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|iu|g|tab|tablet|capsule|cap)s?)\b',
            context_text, re.IGNORECASE
        )
        dosage = dosage_match.group(1) if dosage_match else 'as prescribed'

        frequency = 'once daily'
        times_per_day = 1
        schedule_times = ['08:00']
        for pattern, (freq_text, times, schedule) in freq_patterns.items():
            if re.search(pattern, context_text, re.IGNORECASE):
                frequency = freq_text
                times_per_day = times
                schedule_times = schedule
                break

        instructions = None
        for inst_pattern in instruction_patterns:
            inst_match = re.search(inst_pattern, context_text, re.IGNORECASE)
            if inst_match:
                instructions = inst_match.group(1).strip().capitalize()
                break

        return dosage, frequency, times_per_day, schedule_times, instructions

    def _pattern_rescue(self, lines: list, freq_patterns: dict, instruction_patterns: list) -> list:
        """
        Last-resort extractor: find ANY sequence of (word ≥4 chars)(whitespace)(dosage)
        on the same line, and treat that word as the drug name.
        Works even when the drug name is not in KNOWN_DRUG_NAMES.
        """
        rescued = []
        dosage_re = re.compile(
            r'([A-Za-z]{4,})\s+(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|iu|g))\b',
            re.IGNORECASE
        )
        seen_names: set = set()

        for index, line in enumerate(lines):
            normalized = self._normalize_ocr_compact_text(line)
            # Skip obvious non-medication lines
            if any(kw in normalized.lower() for kw in [
                'doctor', 'patient', 'date', 'hospital', 'clinic',
                'signature', 'address', 'phone', 'license', 'reg'
            ]):
                continue

            for match in dosage_re.finditer(normalized):
                name_candidate = match.group(1).strip()
                dosage_str = match.group(2).replace(' ', '')
                # Skip single-char sequences or known noise words
                if len(name_candidate) < 4:
                    continue
                if name_candidate.lower() in {'take', 'with', 'after', 'before', 'each', 'capsule', 'tablet'}:
                    continue
                # Gather surrounding context for frequency/instructions
                context_parts = [normalized]
                if index + 1 < len(lines):
                    context_parts.append(self._normalize_ocr_compact_text(lines[index + 1]))
                context_text = ' '.join(context_parts)

                _, frequency, times_per_day, schedule_times, instructions = \
                    self._extract_dosage_freq_instructions(context_text, freq_patterns, instruction_patterns)

                key = name_candidate.lower()
                if key not in seen_names:
                    seen_names.add(key)
                    rescued.append(Medication(
                        name=name_candidate.title(),
                        dosage=dosage_str,
                        frequency=frequency,
                        times_per_day=times_per_day,
                        schedule_times=schedule_times,
                        instructions=instructions
                    ))

        if rescued:
            print(f"🔍 Pattern rescue found {len(rescued)} medication(s)")
        return rescued


    async def _try_gemini_fallback(self, prescription_text: str) -> MedicationSchedule | None:
        """Try Gemini as secondary parser only when key is configured and import is available."""
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key or "here" in google_key.lower():
            return None

        try:
            prompt = self.prompt_template.format(prescription_text=prescription_text)
            response_text = await asyncio.to_thread(self._call_gemini_rest, prompt)
            if not response_text:
                return None

            schedule = self._parse_response_to_schedule(response_text)
            return schedule if schedule.total_medications > 0 else None
        except Exception:
            return None

    def _call_gemini_rest(self, prompt: str, image_base64: str | None = None, mime_type: str = "image/jpeg") -> str | None:
        """Call Gemini via REST API with model fallback to avoid SDK/version drift issues."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        # Primary model from env, then ordered fallbacks (newest first)
        primary = os.getenv("GEMINI_VISION_MODEL") if image_base64 else os.getenv("GEMINI_MODEL")
        model_candidates = [m for m in [
            primary,
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ] if m]
        # Deduplicate while preserving order
        seen: set = set()
        model_candidates = [m for m in model_candidates if not (m in seen or seen.add(m))]

        parts = [{"text": prompt}]
        if image_base64:
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_base64,
                }
            })

        payload = {"contents": [{"parts": parts}]}

        for model_name in model_candidates:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                print(f"🔍 Gemini REST trying model: {model_name}")
                response = httpx.post(url, json=payload, timeout=45.0)
                if response.status_code != 200:
                    print(f"⚠️  Gemini REST {model_name} → HTTP {response.status_code}: {response.text[:200]}")
                    continue

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    print(f"⚠️  Gemini REST {model_name} → no candidates in response")
                    continue

                content = candidates[0].get("content", {})
                for part in content.get("parts", []):
                    text = (part.get("text") or "").strip()
                    if text:
                        print(f"✅ Gemini REST {model_name} → got {len(text)} chars")
                        return text
                print(f"⚠️  Gemini REST {model_name} → candidates present but no text part")
            except Exception as exc:
                print(f"⚠️  Gemini REST {model_name} → exception: {exc}")
                continue

        print("❌ Gemini REST: all models exhausted, returning None")
        return None

    def _extract_medications_from_ocr_lines(self, lines: List[str]) -> List[Medication]:
        """Extract medications from OCR lines when exact-name matching is unreliable."""
        extracted: List[Medication] = []
        freq_map = {
            'OD': ('once daily', 1, ['08:00']),
            'BD': ('twice daily', 2, ['08:00', '20:00']),
            'BID': ('twice daily', 2, ['08:00', '20:00']),
            'TID': ('three times daily', 3, ['08:00', '14:00', '20:00']),
            'QID': ('four times daily', 4, ['08:00', '12:00', '16:00', '20:00']),
            'HS': ('once daily at night', 1, ['22:00']),
            'DAILY': ('once daily', 1, ['08:00']),
        }

        dosage_re = re.compile(r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|iu|g))\b', re.IGNORECASE)
        freq_re = re.compile(r'\b(OD|BD|BID|TID|QID|HS|DAILY)\b', re.IGNORECASE)

        for line in lines:
            normalized = self._normalize_ocr_compact_text(line)
            if not self._looks_like_medication_line(normalized):
                continue

            dosage_match = dosage_re.search(normalized)
            if not dosage_match:
                continue

            freq_match = freq_re.search(normalized)
            freq_code = (freq_match.group(1).upper() if freq_match else 'OD')
            frequency, times_per_day, schedule_times = freq_map.get(freq_code, freq_map['OD'])

            # Pull the likely medicine token sequence before dosage.
            name_candidate = normalized[:dosage_match.start()].strip(' -,:.;')
            name_candidate = re.sub(r'^\d+[\).\-\s]*', '', name_candidate).strip()

            # If direct token cleanup is poor, try resolver on full line.
            resolved = self._resolve_drug_name(normalized)
            if resolved:
                med_name = resolved.title()
            else:
                if len(name_candidate) < 3:
                    continue
                med_name = " ".join(name_candidate.split()[:3]).title()

            extracted.append(
                Medication(
                    name=med_name,
                    dosage=dosage_match.group(1),
                    frequency=frequency,
                    times_per_day=times_per_day,
                    schedule_times=schedule_times,
                )
            )

        return extracted

    def _normalize_ocr_compact_text(self, text: str) -> str:
        """Normalize compact OCR text so dosage/frequency regex can match reliably."""
        normalized = text

        # Normalize OCR confusions inside words (helps drug names like Amoxici1lin).
        normalized = re.sub(r'(?<=[A-Za-z])[1Il|](?=[A-Za-z])', 'i', normalized)

        # Normalize common OCR misreads in numeric medication tokens.
        normalized = re.sub(r'(?<=\b)[oO](?=\d)', '0', normalized)
        normalized = re.sub(r'(?<=\d)[oO](?=\b|\s*(?:mg|ml|mcg|iu|g))', '0', normalized)
        normalized = re.sub(r'(?<=\b)[lI](?=\d)', '1', normalized)
        normalized = re.sub(r'(?<=\d)[lI](?=\b|\s*(?:mg|ml|mcg|iu|g))', '1', normalized)
        normalized = re.sub(r'(?<=\d)[sS](?=\b|\s*(?:mg|ml|mcg|iu|g))', '5', normalized)
        normalized = re.sub(r'\b[sS][oO0]{2}(?=\s*(?:mg|ml|mcg|iu|g)\b)', '500', normalized)
        normalized = re.sub(r'\b([0-9])[oO]([0-9])\b', r'\g<1>0\g<2>', normalized)

        # Normalize common OCR misreads in frequency abbreviations.
        normalized = re.sub(r'\b[0oO]D\b', 'OD', normalized)
        normalized = re.sub(r'\b[Tt][1Il|][Dd]\b', 'TID', normalized)
        normalized = re.sub(r'\b[Bb8][1Il|][Dd]\b', 'BID', normalized)
        normalized = re.sub(r'\bQ[1Il|][Dd]\b', 'QID', normalized)
        normalized = re.sub(r'\bH[5sS]\b', 'HS', normalized)

        # Add spaces between letters and numbers in both directions.
        normalized = re.sub(r"([A-Za-z])(\d)", r"\1 \2", normalized)
        normalized = re.sub(r"(\d)([A-Za-z])", r"\1 \2", normalized)

        # Re-compact common dosage units after the above split: "500 mg" -> "500mg".
        normalized = re.sub(r"(\d)\s+(mg|ml|mcg|iu|g)\b", r"\1\2", normalized, flags=re.IGNORECASE)

        # Split compact dosage+frequency forms: "500mgBD" -> "500mg BD".
        normalized = re.sub(
            r"\b(mg|ml|mcg|iu|g)(bd|bid|tid|qid|od|prn|hs|nocte)\b",
            r"\1 \2",
            normalized,
            flags=re.IGNORECASE
        )

        # Ensure known frequency abbreviations are tokenized.
        normalized = re.sub(r"\b(bid|bd|tid|qid|od|prn|hs|nocte)\b", r" \1 ", normalized, flags=re.IGNORECASE)

        # Collapse duplicate spaces created by normalization.
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    
    async def _parse_with_grok(self, prescription_text: str) -> MedicationSchedule:
        """Parse prescription using Grok API"""
        prompt = self.prompt_template.format(prescription_text=prescription_text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a medical AI assistant that extracts medication information from prescriptions and returns only valid JSON."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "model": self.model_name,
            "stream": False,
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"Grok API error: {response.status_code} - {response.text}")
            
            result = response.json()
            response_text = result["choices"][0]["message"]["content"].strip()
            
            return self._parse_response_to_schedule(response_text)
    
    async def _parse_with_openrouter(self, prescription_text: str) -> MedicationSchedule:
        """Parse prescription using OpenRouter API"""
        prompt = self.prompt_template.format(prescription_text=prescription_text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://doctorbot.local",  # Required by OpenRouter
            "X-Title": "DoctorBot"  # Optional but recommended
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a medical AI assistant that extracts medication information from prescriptions and returns only valid JSON."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
            
            result = response.json()
            response_text = result["choices"][0]["message"]["content"].strip()
            
            return self._parse_response_to_schedule(response_text)
    
    async def _parse_with_gemini(self, prescription_text: str) -> MedicationSchedule:
        """Parse prescription using Gemini API with safe text extraction."""
        prompt = self.prompt_template.format(prescription_text=prescription_text)

        def _call_sdk() -> str | None:
            """Call the Gemini SDK and safely extract text without using .text accessor directly."""
            try:
                response = self.model.generate_content(prompt)
                # Safely extract text through parts to avoid ValueError on blocked responses
                for candidate in (response.candidates or []):
                    for part in (getattr(candidate.content, 'parts', None) or []):
                        text = getattr(part, 'text', None)
                        if text and text.strip():
                            return text.strip()
                return None
            except Exception as sdk_err:
                print(f"⚠️  Gemini SDK call error: {sdk_err}")
                return None

        # Try SDK first, then REST fallback
        response_text = await asyncio.to_thread(_call_sdk)

        if not response_text:
            print("⚠️  Gemini SDK returned no text – trying REST API fallback")
            response_text = await asyncio.to_thread(self._call_gemini_rest, prompt)

        if not response_text:
            print("⚠️  Gemini REST exhausted – trying OpenRouter fallback")
            response_text = await self._call_openrouter_rest(self.prompt_template.format(prescription_text=prescription_text))

        if not response_text:
            print("⚠️  OpenRouter also returned no text – using demo mode parser")
            return self._parse_demo_mode(prescription_text)

        try:
            return self._parse_response_to_schedule(response_text)
        except Exception as parse_err:
            print(f"⚠️  AI response JSON parse failed: {parse_err} – using demo mode parser")
            return self._parse_demo_mode(prescription_text)
    
    async def _call_openrouter_rest(self, prompt: str) -> str | None:
        """Call OpenRouter API as a fallback when Gemini quota is exhausted."""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or "here" in api_key.lower():
            print("⚠️  OPENROUTER_API_KEY not configured – skipping OpenRouter fallback")
            return None

        # Prefer a reliable free model; fall back through options
        model_candidates = [
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "deepseek/deepseek-r1-distill-llama-70b:free",
        ]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://doctorbot.local",
            "X-Title": "DoctorBot",
        }

        for model_name in model_candidates:
            try:
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a medical AI assistant. Extract medication information from prescriptions and return only valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1200,
                }
                print(f"🔍 OpenRouter fallback trying model: {model_name}")
                async with httpx.AsyncClient(timeout=40.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                if response.status_code != 200:
                    print(f"⚠️  OpenRouter {model_name} → HTTP {response.status_code}: {response.text[:200]}")
                    continue
                result = response.json()
                text = result["choices"][0]["message"]["content"].strip()
                if text:
                    print(f"✅ OpenRouter {model_name} → got {len(text)} chars")
                    return text
            except Exception as exc:
                print(f"⚠️  OpenRouter {model_name} → exception: {exc}")
                continue

        print("❌ OpenRouter: all models exhausted")
        return None

    def _parse_response_to_schedule(self, response_text: str) -> MedicationSchedule:
        """Convert AI response to MedicationSchedule object.
        
        Handles:
        - Raw JSON responses
        - Markdown code-fenced JSON (```json ... ```)
        - JSON embedded in prose
        """
        # Strip markdown code fences if present
        stripped = re.sub(r'^```(?:json)?\s*', '', response_text.strip(), flags=re.IGNORECASE)
        stripped = re.sub(r'```\s*$', '', stripped.strip())
        stripped = stripped.strip()

        # Extract JSON object from response (handles surrounding prose)
        json_match = re.search(r'\{.*\}', stripped, re.DOTALL)
        if json_match:
            json_text = json_match.group()
        else:
            json_text = stripped

        # Parse JSON
        parsed_data = json.loads(json_text)

        # Convert to Medication objects
        medications = []
        for med_data in parsed_data.get("medications", []):
            name = (med_data.get("name") or "").strip()
            dosage = (med_data.get("dosage") or "as prescribed").strip()
            frequency = (med_data.get("frequency") or "once daily").strip()
            if not name or name.lower() in ("unknown", "n/a", ""):
                continue
            medication = Medication(
                name=name,
                dosage=dosage,
                frequency=frequency,
                times_per_day=med_data.get("times_per_day", 1),
                schedule_times=med_data.get("schedule_times") or ["08:00"],
                instructions=med_data.get("instructions") or None
            )
            medications.append(medication)

        medications = self._deduplicate_medications(medications)

        return MedicationSchedule(
            medications=medications,
            total_medications=len(medications)
        )

    def _deduplicate_medications(self, medications: List[Medication]) -> List[Medication]:
        """Remove duplicate medications while preserving input order."""
        unique_medications: List[Medication] = []
        seen_keys = set()

        for med in medications:
            name = (med.name or "").strip().lower()
            dosage = (med.dosage or "").strip().lower()
            frequency = (med.frequency or "").strip().lower()
            key = (name, dosage, frequency)

            if key in seen_keys:
                continue

            seen_keys.add(key)
            unique_medications.append(med)

        return unique_medications
    
    def _fallback_parsing(self, text: str) -> MedicationSchedule:
        """Fallback parsing using regex patterns"""
        medications = []

        freq_map = {
            'OD': ('once daily', 1, ['08:00']),
            'BD': ('twice daily', 2, ['08:00', '20:00']),
            'BID': ('twice daily', 2, ['08:00', '20:00']),
            'TID': ('three times daily', 3, ['08:00', '14:00', '20:00']),
            'QID': ('four times daily', 4, ['08:00', '12:00', '16:00', '20:00']),
            'HS': ('once daily at night', 1, ['22:00'])
        }

        for raw_line in text.splitlines():
            normalized_line = self._normalize_ocr_compact_text(raw_line)
            if len(normalized_line) < 4:
                continue
            if not self._looks_like_medication_line(normalized_line):
                continue

            drug_name = self._resolve_drug_name(normalized_line)
            if not drug_name:
                continue

            dosage_match = re.search(r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|iu|g))\b', normalized_line, re.IGNORECASE)
            dosage = dosage_match.group(1) if dosage_match else 'as prescribed'

            freq_match = re.search(r'\b(OD|BD|BID|TID|QID|HS|daily)\b', normalized_line, re.IGNORECASE)
            freq_code = (freq_match.group(1).upper() if freq_match else 'OD')
            if freq_code == 'DAILY':
                freq_code = 'OD'

            frequency, times_per_day, schedule_times = freq_map.get(freq_code, ('once daily', 1, ['08:00']))

            medications.append(
                Medication(
                    name=drug_name.title(),
                    dosage=dosage,
                    frequency=frequency,
                    times_per_day=times_per_day,
                    schedule_times=schedule_times
                )
            )

        medications = self._deduplicate_medications(medications)

        return MedicationSchedule(
            medications=medications,
            total_medications=len(medications)
        )

    def _resolve_drug_name(self, text: str) -> str | None:
        """Resolve a likely medication name from noisy OCR text."""
        lowered = text.lower()
        for drug in self.KNOWN_DRUG_NAMES:
            if drug in lowered:
                return drug

        tokens = re.findall(r'[a-zA-Z]{4,}', lowered)
        for token in tokens:
            closest = get_close_matches(token, self.KNOWN_DRUG_NAMES, n=1, cutoff=0.80)
            if closest:
                match = closest[0]
                if token[0] == match[0]:
                    return match

        return None

    def _looks_like_medication_line(self, text: str) -> bool:
        """Heuristic gate to avoid treating headers/signatures as medication lines."""
        lowered = text.lower()

        blocked_prefixes = (
            'rx ', 'dr ', 'doctor', 'date', 'signature', 'patient', 'clinic', 'hospital'
        )
        if lowered.startswith(blocked_prefixes):
            return False

        has_dosage = bool(re.search(r'\d+(?:\.\d+)?\s*(?:mg|ml|mcg|iu|g)\b', lowered))
        has_form = bool(re.search(r'\b(tab|tablet|cap|capsule)\b', lowered))
        has_frequency = bool(re.search(r'\b(od|bd|bid|tid|qid|hs|daily|night)\b', lowered))

        return has_dosage or (has_form and has_frequency)

    def _is_followup_medication_context(self, text: str) -> bool:
        """Return True when a line looks like details for the previous medication, not a new medication entry."""
        lowered = text.lower()
        if self._resolve_drug_name(text):
            return False

        return lowered.startswith((
            'sig', 'instruction', 'instructions', 'duration', 'take', 'with', 'after', 'before', 'avoid', 'do not'
        ))