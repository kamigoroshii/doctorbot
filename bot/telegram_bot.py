import os
import logging
import httpx
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import asyncio
import io
import soundfile as sf
import speech_recognition as sr
from langdetect import detect
from deep_translator import GoogleTranslator

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DoctorBot:
    TELEGRAM_MAX_MESSAGE_LENGTH = 4096

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        self.application = Application.builder().token(self.token).build()
        self.application.bot_data.setdefault("active_reminders", {})
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup bot command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("myreminders", self.reminders_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_prescription_photo))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_prescription_document))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
✨ **Welcome to DoctorBot**

Your smart prescription companion is ready.

**What I can do for you:**
📸 Read handwritten prescriptions from photos
📄 Process documents (PDF, DOC, DOCX, TXT)
💊 Build a clear medication schedule
⚠️ Flag safety issues and possible interactions
⏰ Set up medication reminder alerts

**Quick start:**
1. Send a clear prescription photo or file
2. Review your extracted medication plan
3. Tap **Set Up Reminders** to enable alerts

Use /help for full guidance.
Use /status to check if all services are healthy.

⚠️ **Medical Disclaimer:** DoctorBot is for informational support only and does not replace professional medical advice.
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🆘 **DoctorBot Help**

**Commands:**
• `/start` - Welcome message and introduction
• `/help` - Show this help message  
• `/myreminders` - View your active medication reminders

**How to use:**
1. **Send Prescription Photo** 📸
   - Take a clear photo of your prescription
   - Send it directly in this chat
   - I'll process it automatically

2. **Send Prescription Document** 📄
   - Upload PDF, DOC, DOCX, or TXT files
   - Digital prescriptions or scanned documents
   - Supports files up to 20MB

3. **Review Results** 📋
   - Check the extracted medication schedule
   - Read any safety warnings
   - Confirm if everything looks correct

3. **Set Reminders** ⏰
   - Choose to enable automatic reminders
   - I'll send you notifications when it's time to take your medicine

**Tips for best results:**
• **Photos**: Ensure good lighting and keep prescription flat
• **Documents**: Use clear scans or digital prescriptions
• **File Types**: JPG, PNG, PDF, DOC, DOCX, TXT supported
• Include the entire prescription in the frame
• Include the entire prescription in the frame

**Safety Features:**
• Drug interaction warnings
• Dosage verification
• Clear medication schedules
• Reminder confirmations

Need help? Just ask me anything!
        """
        
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myreminders command"""
        user_id = str(update.effective_user.id)
        active_reminders = context.application.bot_data.get("active_reminders", {})
        reminders = active_reminders.get(user_id, [])

        if not reminders:
            reminder_message = (
                "⏰ **Your Active Reminders**\n\n"
                "You don't have active medication reminders yet.\n\n"
                "To create reminders:\n"
                "1. Send a prescription photo/document\n"
                "2. Tap **Set Up Reminders**\n"
                "3. I'll send alerts at scheduled times"
            )
            reminder_message = await self.translate_text(reminder_message, context)
            await update.message.reply_text(reminder_message, parse_mode='Markdown')
            return

        message = "⏰ **Your Active Reminders**\n\n"
        for idx, reminder in enumerate(reminders, 1):
            message += (
                f"{idx}. **{reminder['medication']}**\n"
                f"   💊 {reminder['dosage']}\n"
                f"   🕐 Daily at {reminder['time']}\n\n"
            )

        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_prescription_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle prescription photo uploads"""
        user_name = update.message.from_user.first_name or "there"
        try:
            # Send processing message
            message_text = f"📸 Got it, {user_name}! Analysing your prescription...\n⏳ This may take a few moments."
            message_text = await self.translate_text(message_text, context)
            processing_msg = await update.message.reply_text(message_text)
            
            # Get the largest photo size
            photo = update.message.photo[-1]
            
            # Download the photo
            file = await context.bot.get_file(photo.file_id)
            photo_data = await file.download_as_bytearray()
            
            # Convert bytearray to bytes for API compatibility
            photo_bytes = bytes(photo_data)
            
            # Process prescription via API
            result = await self.process_prescription_api(photo_bytes)
            
            # Delete processing message
            await processing_msg.delete()
            
            if result["success"]:
                await self.send_prescription_results(update, context, result)
            else:
                error_type = result.get("error_type", "unknown")
                if error_type == "backend_down":
                    await update.message.reply_text(
                        "🔴 *Backend server is not reachable.*\n\n"
                        "The processing server appears to be offline.\n"
                        "Please ask the admin to run: `python main.py backend`\n\n"
                        "Then try again! 🙏",
                        parse_mode='Markdown'
                    )
                elif error_type == "api_key_error":
                    await update.message.reply_text(
                        "🔑 *AI API Key Error*\n\n"
                        "The AI service API key is invalid or has no credits remaining.\n"
                        "Please check your `.env` file and update the API key.\n\n"
                        "Use /status to diagnose further.",
                        parse_mode='Markdown'
                    )
                elif error_type == "ocr_failed":
                    await update.message.reply_text(
                        "📷 *Could not read the prescription image.*\n\n"
                        "Please try again with a better photo:\n"
                        "• ☀️ Ensure good lighting — no shadows or glare\n"
                        "• 📐 Keep the prescription flat and fully in frame\n"
                        "• 🔍 Make sure text is sharp and not blurry\n"
                        "• 📏 Hold your camera steady closer to the paper\n\n"
                        "Tip: A scan or PDF usually works better than a photo!",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ *Could not process your prescription.*\n\n"
                        f"Reason: {result.get('error', 'Unknown error')}\n\n"
                        "Please try again or use /status to check system health.",
                        parse_mode='Markdown'
                    )
                
        except Exception as e:
            logger.error(f"Error processing prescription: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred while processing your prescription.\n"
                "Please try again or use /status to check system health."
            )
    
    async def handle_prescription_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle prescription document uploads (PDF, DOC, etc.)"""
        try:
            user_name = update.message.from_user.first_name or "there"
            document = update.message.document
            
            # Check file type
            allowed_types = ['application/pdf', 'application/msword', 
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'text/plain', 'image/jpeg', 'image/png']
            
            if document.mime_type not in allowed_types:
                await update.message.reply_text(
                    "❌ Unsupported file type. Please send:\n"
                    "• PDF files (.pdf)\n"
                    "• Word documents (.doc, .docx)\n" 
                    "• Text files (.txt)\n"
                    "• Images (.jpg, .png)"
                )
                return
            
            # Check file size (max 20MB)
            if document.file_size > 20 * 1024 * 1024:
                await update.message.reply_text(
                    "❌ File too large. Please send files smaller than 20MB."
                )
                return
            
            # Send processing message
            message_text = f"📄 Got it, {user_name}! Processing your document: {document.file_name}\n⏳ This may take a few moments."
            message_text = await self.translate_text(message_text, context)
            processing_msg = await update.message.reply_text(message_text)
            
            # Download the document
            file = await context.bot.get_file(document.file_id)
            document_data = await file.download_as_bytearray()
            
            # Convert bytearray to bytes for API compatibility
            document_bytes = bytes(document_data)
            
            # Process document via API
            result = await self.process_document_api(document_bytes, document.mime_type, document.file_name)
            
            # Delete processing message
            await processing_msg.delete()
            
            if result["success"]:
                # Format and send the results
                await self.send_prescription_results(update, context, result)
            else:
                error_type = result.get("error_type", "unknown")
                if error_type == "backend_down":
                    await update.message.reply_text(
                        "🔴 *Backend server is not reachable.*\n\n"
                        "The processing server appears to be offline.\n"
                        "Please run: `python main.py` or `python main.py backend`\n\n"
                        "Then send the document again.",
                        parse_mode='Markdown'
                    )
                elif error_type == "api_key_error":
                    await update.message.reply_text(
                        "🔑 *AI API Key Error*\n\n"
                        "The AI service API key is invalid or has no credits remaining.\n"
                        "Please check your `.env` file and test with /status.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ *Could not process your document.*\n\n"
                        f"Reason: {result.get('error', 'Unknown error')}\n\n"
                        "If this is a text file, make sure it contains readable prescription text.\n"
                        "Use /status to verify backend and AI status.",
                        parse_mode='Markdown'
                    )
                
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            await update.message.reply_text(
                "❌ An error occurred while processing your document. Please try again."
            )
    
    async def check_backend_health(self) -> dict:
        """Check if backend server is reachable and AI key is valid"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_base_url}/health")
                if response.status_code == 200:
                    return response.json()
                return {"status": "error", "detail": f"HTTP {response.status_code}"}
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return {"status": "backend_down", "detail": "Cannot reach backend server"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def process_prescription_api(self, photo_data: bytes) -> dict:
        """Send photo to backend API for processing"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                files = {"file": ("prescription.jpg", photo_data, "image/jpeg")}
                response = await client.post(
                    f"{self.api_base_url}/process-prescription",
                    files=files
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 503:
                    return {"success": False, "error_type": "api_key_error", "error": "AI service unavailable (API key invalid or no credits)"}
                elif response.status_code == 422:
                    detail = ""
                    try:
                        detail = response.json().get("detail", "")
                    except Exception:
                        pass
                    if detail == "__OCR_FAILED__":
                        return {"success": False, "error_type": "ocr_failed", "error": "Image quality too low"}
                    return {"success": False, "error_type": "ocr_failed", "error": detail or "Could not read prescription"}
                else:
                    error_detail = ""
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except Exception:
                        error_detail = response.text
                    return {"success": False, "error_type": "processing_error", "error": error_detail}
                    
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            logger.error("API request failed: Backend server not reachable")
            return {"success": False, "error_type": "backend_down", "error": "Backend server is not running"}
        except httpx.ReadTimeout:
            logger.error("API request failed: Processing timeout")
            return {"success": False, "error_type": "timeout", "error": "Image is taking too long to process (likely due to OCR). Try a clearer, cropped photo."}
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {"success": False, "error_type": "unknown", "error": str(e) or "Unknown internal error"}
    
    async def process_document_api(self, document_data: bytes, mime_type: str, filename: str) -> dict:
        """Send document to backend API for processing"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for documents
                files = {"file": (filename, document_data, mime_type)}
                response = await client.post(
                    f"{self.api_base_url}/process-document",
                    files=files
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 503:
                    return {"success": False, "error_type": "api_key_error", "error": "AI service unavailable (API key invalid or no credits)"}
                else:
                    error_detail = ""
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except Exception:
                        error_detail = response.text
                    return {"success": False, "error_type": "processing_error", "error": error_detail}
                    
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            logger.error("Document API request failed: Backend server not reachable")
            return {"success": False, "error_type": "backend_down", "error": "Backend server is not running"}
        except Exception as e:
            logger.error(f"Document API request failed: {str(e)}")
            return {"success": False, "error_type": "unknown", "error": str(e)}
    
    async def send_prescription_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict):
        """Format and send prescription processing results"""
        try:
            schedule = result["medication_schedule"]
            warnings = result.get("warnings", [])
            extraction_method = result.get("extraction_method")
            extraction_confidence = result.get("extraction_confidence")
            extraction_summary = result.get("extraction_summary", {})
            extracted_text = result.get("extracted_text", "")

            if schedule.get("total_medications", 0) == 0:
                warning_msg = (
                    "⚠️ I could read the prescription image, but I couldn't confidently detect medication names.\n\n"
                    "Please try again with a clearer photo:\n"
                    "• Keep the paper straight (not rotated)\n"
                    "• Use brighter lighting\n"
                    "• Keep all text in frame\n"
                    "• Move closer so medicine names are sharp\n\n"
                    "You can also upload a typed PDF/TXT for better accuracy."
                )
                warning_msg = await self.translate_text(warning_msg, context)
                await update.message.reply_text(warning_msg)
                return

            # Store latest parsed schedule for one-tap reminder setup.
            context.user_data["latest_schedule"] = schedule
            
            # Create medication schedule message
            message = "✅ **Prescription Processed Successfully!**\n\n"
            if extraction_method:
                message += f"🧠 **Extraction Method:** {extraction_method}\n"
            if extraction_confidence is not None:
                message += f"📈 **Extraction Confidence:** {float(extraction_confidence):.2f}\n"
            if extraction_method or extraction_confidence is not None:
                message += "\n"
            message += f"📋 **Medication Schedule** ({schedule['total_medications']} medications):\n\n"

            if extracted_text and extracted_text not in ["[Parsed directly from image with Gemini Vision fallback]"]:
                preview_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()][:4]
                if preview_lines:
                    message += "🧾 **OCR Evidence**:\n"
                    for line in preview_lines:
                        message += f"   • {line[:90]}\n"
                    message += "\n"
            
            for i, med in enumerate(schedule["medications"], 1):
                message += f"**{i}. {med['name']}**\n"
                message += f"   💊 Dosage: {med['dosage']}\n"
                message += f"   🕐 Frequency: {med['frequency']}\n"
                message += f"   ⏰ Times: {', '.join(med['schedule_times'])}\n"
                if med.get('duration'):
                    message += f"   📅 Duration: {med['duration']}\n"
                if med.get('instructions'):
                    message += f"   📝 Instructions: {med['instructions']}\n"
                if med.get('source_line'):
                    message += f"   🔎 Source: {med['source_line'][:90]}\n"
                message += "\n"

            if extraction_confidence is not None and float(extraction_confidence) < 0.75:
                message += (
                    "⚠️ **Low-confidence note:** the medicine name may need a quick manual check.\n\n"
                )

            if extraction_summary and extraction_summary.get("entities"):
                message += "🧠 **Extraction Candidates:**\n"
                for entity in extraction_summary.get("entities", [])[:3]:
                    message += (
                        f"   • {entity.get('name')} | {entity.get('dosage')} | {entity.get('frequency')}"
                        f" | {entity.get('matched_by', 'unknown')}\n"
                    )
                message += "\n"
            
            # Add warnings if any
            if warnings:
                message += "⚠️ **Safety Warnings:**\n\n"
                for warning in warnings:
                    severity_emoji = "🔴" if warning["severity"] == "high" else "🟡"
                    message += f"{severity_emoji} {warning['message']}\n\n"
            
            # Add reminder setup buttons
            keyboard = [
                [InlineKeyboardButton("✅ Set Up Reminders", callback_data="setup_reminders")],
                [InlineKeyboardButton("📋 View Full Details", callback_data="view_details")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Auto-translate to the user's native language!
            message = await self.translate_text(message, context)

            chunks = self._split_for_telegram(message)
            for index, chunk in enumerate(chunks):
                is_last_chunk = index == len(chunks) - 1
                await self._send_chunk_with_fallback(
                    update,
                    chunk,
                    reply_markup=reply_markup if is_last_chunk else None
                )
            
        except Exception as e:
            logger.error(f"Error sending results: {str(e)}")
            await update.message.reply_text("❌ Error formatting results. Please try again.")

    async def _send_chunk_with_fallback(self, update: Update, chunk: str, reply_markup=None):
        """Send a result chunk with Markdown, falling back to plain text if needed."""
        try:
            await update.message.reply_text(
                chunk,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except BadRequest as exc:
            logger.warning(f"Markdown send failed, retrying without Markdown: {exc}")
            await update.message.reply_text(
                chunk,
                reply_markup=reply_markup
            )

    async def _send_medication_reminder(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a scheduled medication reminder notification."""
        job_data = context.job.data or {}
        medication = job_data.get("medication", "Medication")
        dosage = job_data.get("dosage", "as prescribed")
        reminder_time = job_data.get("time", "scheduled time")
        instructions = job_data.get("instructions")

        message = (
            "⏰ **Medication Reminder**\n\n"
            f"💊 **{medication}**\n"
            f"Dosage: {dosage}\n"
            f"Scheduled: {reminder_time}\n"
        )

        if instructions:
            message += f"Instructions: {instructions}\n"

        message += "\n✅ Please take your medication if due."

        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=message,
            parse_mode="Markdown"
        )

    async def _setup_user_reminders(self, query, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Create daily reminder jobs from latest parsed schedule.

        Returns:
            -1 when scheduler is unavailable
             0 when no schedule exists
            >0 number of created jobs
        """
        if context.job_queue is None:
            logger.error("Reminder setup failed: JobQueue is not available. Install APScheduler/job-queue extras.")
            return -1

        schedule = context.user_data.get("latest_schedule")
        if not schedule:
            return 0

        user_id = str(query.from_user.id)
        chat_id = query.message.chat_id

        # Remove existing jobs for this user to avoid duplicate alerts.
        existing_jobs = context.job_queue.get_jobs_by_name(f"reminder:{user_id}")
        for job in existing_jobs:
            job.schedule_removal()

        reminder_registry = []
        jobs_created = 0

        for medication in schedule.get("medications", []):
            med_name = medication.get("name", "Medication")
            dosage = medication.get("dosage", "as prescribed")
            instructions = medication.get("instructions")

            for scheduled in medication.get("schedule_times", []):
                try:
                    hour, minute = map(int, scheduled.split(":"))
                    when = time(hour=hour, minute=minute)
                except Exception:
                    continue

                context.job_queue.run_daily(
                    self._send_medication_reminder,
                    time=when,
                    days=(0, 1, 2, 3, 4, 5, 6),
                    chat_id=chat_id,
                    name=f"reminder:{user_id}",
                    data={
                        "medication": med_name,
                        "dosage": dosage,
                        "time": scheduled,
                        "instructions": instructions,
                    }
                )
                reminder_registry.append(
                    {"medication": med_name, "dosage": dosage, "time": scheduled}
                )
                jobs_created += 1

        context.application.bot_data.setdefault("active_reminders", {})
        context.application.bot_data["active_reminders"][user_id] = reminder_registry

        return jobs_created

    def _split_for_telegram(self, message: str, max_length: int = 3800) -> list[str]:
        """Split message into Telegram-safe chunks while preserving formatting blocks."""
        if len(message) <= max_length:
            return [message]

        chunks: list[str] = []
        current = ""

        # Prefer splitting on paragraph boundaries to avoid breaking Markdown formatting.
        for paragraph in message.split("\n\n"):
            block = paragraph + "\n\n"

            if len(block) > max_length:
                # Paragraph is too long, split by lines then hard-split if needed.
                for line in paragraph.split("\n"):
                    line_block = line + "\n"

                    if len(line_block) > max_length:
                        if current:
                            chunks.append(current.rstrip())
                            current = ""

                        start = 0
                        while start < len(line_block):
                            end = start + max_length
                            chunks.append(line_block[start:end].rstrip())
                            start = end
                        continue

                    if len(current) + len(line_block) > max_length:
                        chunks.append(current.rstrip())
                        current = line_block
                    else:
                        current += line_block

                if current and not current.endswith("\n\n"):
                    if len(current) + 1 > max_length:
                        chunks.append(current.rstrip())
                        current = "\n"
                    else:
                        current += "\n"
                continue

            if len(current) + len(block) > max_length:
                chunks.append(current.rstrip())
                current = block
            else:
                current += block

        if current.strip():
            chunks.append(current.rstrip())

        return chunks if chunks else [message]
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        async def safe_edit(text: str, **kwargs):
            """Edit message text, silently ignoring 'Message is not modified' errors."""
            try:
                await query.edit_message_text(text, **kwargs)
            except BadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    pass  # User tapped the same button twice — harmless
                else:
                    logger.warning(f"edit_message_text BadRequest: {exc}")
            except Exception as exc:
                logger.warning(f"edit_message_text failed: {exc}")

        if query.data == "setup_reminders":
            created = await self._setup_user_reminders(query, context)
            if created == -1:
                await safe_edit(
                    "⚠️ Reminder scheduler is not available on the server right now.\n\n"
                    "Please ask the admin to install dependencies and restart:\n"
                    "`pip install -r requirements.txt`",
                    parse_mode="Markdown"
                )
            elif created == 0:
                await safe_edit(
                    "⚠️ I couldn't find a recent medication schedule to set reminders.\n\n"
                    "Please upload a prescription first, then tap *Set Up Reminders*.",
                    parse_mode="Markdown"
                )
            else:
                await safe_edit(
                    "⏰ *Reminders Set Up Successfully!*\n\n"
                    f"Created *{created}* daily reminder alerts.\n"
                    "Use /myreminders to view active reminders.\n\n"
                    "✅ Real-time alerts are now active.",
                    parse_mode="Markdown"
                )
        elif query.data == "view_details":
            await safe_edit(
                "📋 *Detailed Information*\n\n"
                "For detailed medication information, drug interactions, and side effects, "
                "please consult your healthcare provider or pharmacist.\n\n"
                "This bot provides basic scheduling and reminder services only.",
                parse_mode="Markdown"
            )
        elif query.data == "cancel":
            await safe_edit("❌ Operation cancelled.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - check backend and AI API health"""
        checking_msg = await update.message.reply_text("🔍 Checking system status...")
        
        health = await self.check_backend_health()
        status = health.get("status", "unknown")
        
        if status == "backend_down":
            msg = (
                "🔴 *System Status*\n\n"
                "❌ Backend Server: *OFFLINE*\n"
                "Please run: `python main.py backend`\n\n"
                "🤖 Bot: ✅ Running"
            )
        elif status == "ok":
            ai_status = health.get("ai_status", "unknown")
            ai_provider = health.get("ai_provider", "unknown")
            ai_emoji = "✅" if ai_status == "ok" else "❌"
            credits = health.get("credits", "N/A")
            msg = (
                f"🟢 *System Status*\n\n"
                f"✅ Backend Server: *ONLINE*\n"
                f"{ai_emoji} AI Provider ({ai_provider}): *{ai_status.upper()}*\n"
                f"💳 Credits/Tokens: {credits}\n"
                f"🤖 Bot: ✅ Running"
            )
            if ai_status != "ok":
                msg += "\n\n⚠️ Your AI API key may be invalid or out of credits.\nCheck your `.env` file."
        else:
            msg = (
                "🟡 *System Status*\n\n"
                f"⚠️ Backend: {health.get('detail', 'Unknown error')}\n"
                "🤖 Bot: ✅ Running"
            )
        
        await checking_msg.delete()
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def translate_text(self, text: str, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Helper to seamlessly translate outgoing message blocks to the user's detected language."""
        lang = context.user_data.get('lang', 'en')
        if lang in ['en', 'unknown'] or not lang:
            return text
        try:
            return await asyncio.to_thread(lambda: GoogleTranslator(source='en', target=lang).translate(text))
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages and DETECT LANGUAGE automatically"""
        text = update.message.text
        
        # Determine language so we can translate future reports!
        try:
            detected_lang = detect(text)
            if detected_lang != context.user_data.get('lang'):
                context.user_data['lang'] = detected_lang
                logger.info(f"Set user {update.effective_user.id} language to {detected_lang}")
        except Exception as e:
            pass

        text_lower = text.lower()
        if any(word in text_lower for word in ['help', 'how', 'what', 'guide']):
            await self.help_command(update, context)
        elif any(word in text_lower for word in ['status', 'check', 'working', 'online']):
            await self.status_command(update, context)
        else:
            msg = (
                "👋 I can help with prescriptions.\n\n"
                "📸 Send a clear prescription photo\n"
                "📄 Or upload a document (PDF, DOC, DOCX, TXT)\n\n"
                "Use /start to see the full welcome guide.\n"
                "Use /help for commands and tips.\n"
                "Use /status to check system health."
            )
            msg = await self.translate_text(msg, context)
            await update.message.reply_text(msg)

    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming voice messages by transcribing them to text"""
        status_msg = await update.message.reply_text("🎙️ Listening to your voice note...")
        try:
            # Get voice file from Telegram (comes as .ogg)
            voice_file = await update.message.voice.get_file()
            byte_stream = io.BytesIO()
            await voice_file.download_to_memory(byte_stream)
            byte_stream.seek(0)
            
            # Convert OGG to WAV in memory using soundfile
            # This completely bypasses the need for FFmpeg on the system
            data, samplerate = sf.read(byte_stream)
            wav_stream = io.BytesIO()
            sf.write(wav_stream, data, samplerate, format='WAV', subtype='PCM_16')
            wav_stream.seek(0)
            
            # Run SpeechRecognition in a separate thread so it doesn't block the async loop
            def _recognize():
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_stream) as source:
                    audio_data = recognizer.record(source)
                    return recognizer.recognize_google(audio_data)
                    
            text = await asyncio.to_thread(_recognize)
            await status_msg.edit_text(f"🗣️ **Transcription:**\n\n_{text}_", parse_mode='Markdown')
            
        except sr.UnknownValueError:
            await status_msg.edit_text("⚠️ Could not understand the audio. Please speak clearly.")
        except sr.RequestError as e:
            await status_msg.edit_text("⚠️ Speech recognition service is currently unavailable.")
        except Exception as e:
            logger.error(f"Voice to text error: {e}")
            await status_msg.edit_text("❌ Error processing voice note.")

    def run(self):
        """Start the bot"""
        logger.info("Starting DoctorBot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = DoctorBot()
    bot.run()