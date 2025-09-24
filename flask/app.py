import os
import json
import time
import re
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader, JSONLoader
from langchain_huggingface import HuggingFaceEmbeddings


# -------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# --- Default email for all reminders
DEFAULT_REMINDER_EMAIL = "your_default_email@example.com"

REMINDERS_FILE = "reminders.txt"
SENT_LOG = "sent_reminders.txt"
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)


# -------------------------------------------------------------------
# Initialize Flask App and Scheduler
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
scheduler = BackgroundScheduler()
scheduler.start()


# -------------------------------------------------------------------
# LLM & Prompt Template for Q&A
# -------------------------------------------------------------------
def initialize_llm():
    model = "llama-3.1-8b-instant"
    return ChatGroq(
        groq_api_key=groq_api_key,
        model_name=model
    )

def initialize_prompt():
    return ChatPromptTemplate.from_template("""
    You are CampusCopilot, an AI Companion for students, providing **strictly accurate and helpful information based on official college data sources.

    STRICT RESPONSE GUIDELINES:
    1. Use ONLY the provided college data to answer queries. No assumptions.
    2. Directly present the relevant information.
    3. If unavailable, reply with:
        "Information not available in the current database."
    4. If related but missing, reply with:
        "This information is currently not available. For assistance, please contact the college helpdesk or refer to official resources."
    5. Provide a clear and complete answer.

    Official College Data Sources:
    {context}

    Query: {input}
    """)


# -------------------------------------------------------------------
# Vector Database (FAISS) for Q&A
# -------------------------------------------------------------------
vectors = None          # FAISS vector store
llm_qa_chain = None     # LLM + retrieval chain for Q&A
retrieval_chain = None

# def process_documents():
#     global vectors, llm_qa_chain
#     try:
#         embeddings = HuggingFaceEmbeddings(
#             model_name="sentence-transformers/all-MiniLM-L6-v2"
#         )
#         loader = PyPDFDirectoryLoader("../data")
#         docs = loader.load()
#         if not docs:
#             print("⚠ No PDF documents found in ../data")
#             return False
#         splitter = RecursiveCharacterTextSplitter(
#             chunk_size=2000, chunk_overlap=200
#         )
#         final_docs = splitter.split_documents(docs)
#         vectors = FAISS.from_documents(final_docs, embeddings)
        
#         llm = initialize_llm()
#         document_chain = create_stuff_documents_chain(llm, initialize_prompt())
#         llm_qa_chain = create_retrieval_chain(vectors.as_retriever(), document_chain)
        
#         return True
#     except Exception as e:
#         print(f"❌ Vector DB init error: {e}")
#         return False

def process_documents():
    """Load PDFs and JSONs, split into chunks, and create FAISS vector DB."""
    global vectors, retrieval_chain, llm_qa_chain
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # Load PDFs
        pdf_loader = PyPDFDirectoryLoader("../data", recursive=True)
        pdf_docs = pdf_loader.load()
        for doc in pdf_docs:
            doc.metadata["source"] = getattr(doc, "file_path", "unknown")

        # Load JSONs
        json_docs = []
        for root, _, files in os.walk("../data"):
            for filename in files:
                if filename.endswith(".json"):
                    loader = JSONLoader(file_path=os.path.join(root, filename),
                                        jq_schema=".", text_content=False)
                    loaded_docs = loader.load()
                    for doc in loaded_docs:
                        doc.metadata["source"] = filename
                    json_docs.extend(loaded_docs)

        docs = pdf_docs + json_docs
        if not docs:
            print("⚠ No documents found in ../data")
            return False

        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=250)
        final_docs = splitter.split_documents(docs)

        # Create FAISS vector store
        vectors = FAISS.from_documents(final_docs, embeddings)

        # Initialize LLM + retrieval chain
        llm = initialize_llm()
        doc_chain = create_stuff_documents_chain(llm, initialize_prompt())
        retriever = vectors.as_retriever(search_kwargs={"k": 8})
        retrieval_chain = create_retrieval_chain(retriever, doc_chain)

        # Assign to llm_qa_chain so /chat endpoint works
        llm_qa_chain = retrieval_chain

        print(f"✅ Loaded {len(final_docs)} document chunks into FAISS")
        return True

    except Exception as e:
        print(f"❌ Vector DB init error: {e}")
        return False


if process_documents():
    print("Vector database initialized successfully")
else:
    print("Failed to initialize vector database")


# -------------------------------------------------------------------
# Utility functions for Reminders
# -------------------------------------------------------------------
def load_reminders():
    reminders = []
    if not os.path.exists(REMINDERS_FILE):
        return reminders
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                reminders.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return reminders

def append_reminder_to_file(reminder):
    with open(REMINDERS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(reminder, default=str, ensure_ascii=False) + "\n")

def write_sent_log(entry):
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")

def parse_offset_text(offset_text: str):
    """Parse offset text like '5 days', '2 hours', etc."""
    if not offset_text:
        return timedelta(days=1)  # Default to 1 day before
    
    s = offset_text.lower().strip()
    
    # Enhanced regex to capture various patterns
    patterns = [
        r"(\d+)\s*(day|days|din)",
        r"(\d+)\s*(hour|hours|hrs|ghanta|ghante)",
        r"(\d+)\s*(week|weeks|hafta|hafte)",
        r"(\d+)\s*(minute|minutes|min|mints)",
        r"(\d+)\s*(month|months|mahina|mahine)"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            num = int(m.group(1))
            unit = m.group(2).lower()
            
            if unit.startswith("day") or unit == "din":
                return timedelta(days=num)
            elif unit.startswith("hour") or unit in ["hrs", "ghanta", "ghante"]:
                return timedelta(hours=num)
            elif unit.startswith("minute") or unit in ["min", "mints"]:
                return timedelta(minutes=num)
            elif unit.startswith("week") or unit in ["hafta", "hafte"]:
                return timedelta(weeks=num)
            elif unit.startswith("month") or unit in ["mahina", "mahine"]:
                return timedelta(days=30 * num)
    
    return timedelta(days=1)  # Default fallback

def extract_reminder_info(message):
    """Extract reminder information from user message"""
    
    # Check if it's a reminder request
    reminder_keywords = [
        r"\b(yaad\s*dilana|remind\s*me|notify\s*me|alert\s*me|yaad\s*karo|reminder)\b",
        r"\b(set\s*reminder|schedule\s*reminder)\b"
    ]
    
    is_reminder = False
    for keyword in reminder_keywords:
        if re.search(keyword, message, re.IGNORECASE):
            is_reminder = True
            break
    
    if not is_reminder:
        return None, None, None
    
    # Extract offset (time before event)
    offset_patterns = [
        r"(\d+)\s*(day|days|din|dino?)\s*(pehle|before)",
        r"(\d+)\s*(hour|hours|ghanta|ghante)\s*(pehle|before)",
        r"(\d+)\s*(week|weeks|hafta|hafte)\s*(pehle|before)",
        r"(\d+)\s*(minute|minutes|min)\s*(pehle|before)",
        r"(pehle|before)\s*(\d+)\s*(day|days|din|dino?)",
        r"(pehle|before)\s*(\d+)\s*(hour|hours|ghanta|ghante)"
    ]
    
    offset_text = None
    for pattern in offset_patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            if m.group(1).isdigit():
                offset_text = f"{m.group(1)} {m.group(2)}"
            else:
                offset_text = f"{m.group(2)} {m.group(3)}"
            break
    
    # Extract event description - improved logic
    event_description = None
    
    # Try to extract event description from common patterns
    patterns = [
        r"(?:yaad\s*dilana|remind\s*me|notify\s*me)\s+(?:about\s+)?(.+?)(?:\s+\d+\s*(?:day|days|hour|hours|pehle|before)|$)",
        r"(?:set\s*reminder\s+for|reminder\s+for)\s+(.+?)(?:\s+\d+\s*(?:day|days|hour|hours|pehle|before)|$)",
        r"(.+?)\s+(?:ke\s+liye|ka)\s+(?:yaad\s*dilana|reminder)",
        r"(.+?)\s+(?:\d+\s*(?:day|days|hour|hours|pehle|before))"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            event_description = m.group(1).strip(" .,;:!?")
            break
    
    # If no specific pattern matches, extract the main content
    if not event_description:
        # Remove reminder keywords and extract main content
        cleaned_message = message
        for keyword in ["yaad dilana", "remind me", "notify me", "set reminder", "reminder"]:
            cleaned_message = re.sub(keyword, "", cleaned_message, flags=re.IGNORECASE)
        
        # Remove offset text
        if offset_text:
            for pattern in offset_patterns:
                cleaned_message = re.sub(pattern, "", cleaned_message, flags=re.IGNORECASE)
        
        event_description = cleaned_message.strip(" .,;:!?")
    
    return True, event_description, offset_text

def resolve_event_date(event_description: str):
    """Resolve event date from description or PDFs"""
    
    if not event_description:
        return None
    
    # First, look for explicit dates in the description
    date_patterns = [
        r"\b(20\d{2}-\d{2}-\d{2})\b",  # ISO format
        r"\b(\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b",  # MM/DD/YYYY or DD/MM/YYYY
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})\b",  # 15 Jan 2025
    ]
    
    for pattern in date_patterns:
        m = re.search(pattern, event_description, re.IGNORECASE)
        if m:
            try:
                parsed_date = dateparser.parse(m.group(1))
                if parsed_date:
                    return parsed_date.date().isoformat()
            except:
                continue
    
    # Query the PDF database for event dates with enhanced patterns
    if llm_qa_chain is not None:
        try:
            query_variations = [
                f"What is the exact date or date range for {event_description}?",
                f"When is {event_description} scheduled?",
                f"Find the examination dates for {event_description}",
                f"What are the dates mentioned for {event_description}?",
                f"Give me the schedule for {event_description}"
            ]
            
            for query in query_variations:
                response = llm_qa_chain.invoke({"input": query})
                result = response.get("answer", "").strip()
                
                app.logger.info(f"LLM response for '{query}': {result}")
                
                # Enhanced date extraction patterns for various formats
                enhanced_patterns = [
                    r"\b(20\d{2}-\d{2}-\d{2})\b",  # ISO format
                    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})\b",  # 11th October 2025
                    r"\b(\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b",  # MM/DD/YYYY
                    r"from\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})",  # from 11th October 2025
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)",  # 11th October (current year assumed)
                ]
                
                # Look for dates in the response
                for pattern in enhanced_patterns:
                    matches = re.findall(pattern, result, re.IGNORECASE)
                    for match in matches:
                        try:
                            # If no year is present, assume current academic year
                            if not re.search(r"20\d{2}", match):
                                match = f"{match} 2025"
                            
                            parsed_date = dateparser.parse(match)
                            if parsed_date and parsed_date.year >= 2024:
                                # Check if this date makes sense (not in the past for future events)
                                if parsed_date.date() >= datetime.now().date():
                                    app.logger.info(f"Found valid future date: {parsed_date.date().isoformat()}")
                                    return parsed_date.date().isoformat()
                                else:
                                    app.logger.info(f"Found past date: {parsed_date.date().isoformat()}, continuing search...")
                        except Exception as e:
                            app.logger.warning(f"Failed to parse date '{match}': {e}")
                            continue
                
                # Look for date ranges and pick the start date
                range_patterns = [
                    r"from\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]\s+20\d{2})\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]\s+20\d{2})",
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]\s+20\d{2})\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]\s+20\d{2})",
                ]
                
                for pattern in range_patterns:
                    match = re.search(pattern, result, re.IGNORECASE)
                    if match:
                        try:
                            start_date = dateparser.parse(match.group(1))
                            if start_date and start_date.year >= 2024 and start_date.date() >= datetime.now().date():
                                app.logger.info(f"Found valid start date from range: {start_date.date().isoformat()}")
                                return start_date.date().isoformat()
                        except Exception as e:
                            app.logger.warning(f"Failed to parse range start date: {e}")
                            continue
                    
        except Exception as e:
            app.logger.warning("LLM QA call failed for date resolution: %s", e)

    # Try fuzzy parsing on the entire description (but be more careful)
    try:
        parsed_date = dateparser.parse(event_description, fuzzy=True)
        if parsed_date and parsed_date.year >= 2024 and parsed_date.date() >= datetime.now().date():
            app.logger.info(f"Fuzzy parsing found future date: {parsed_date.date().isoformat()}")
            return parsed_date.date().isoformat()
    except:
        pass

    # Enhanced fallback mappings for common academic events
    fallback_map = {
        # Mid semester exams
        "mid semester examination (odd semester 2025-26)": "2025-10-11",
        "mid semester exam": "2025-10-11",
        "midsem": "2025-10-11",
        "mid sem": "2025-10-11",
        
        # End semester 
        "end semester examination": "2025-12-15",
        "final exam": "2025-12-15",
        "semester end": "2025-05-30",
        "semester start": "2025-01-15",
        
        # General
        "exam": "2025-10-11",  # Default to upcoming mid-sem
        "assignment submission": "2025-04-30",
        "project deadline": "2025-04-25",
        "registration": "2025-01-10"
    }
    
    event_lower = event_description.lower().strip()
    
    # Check for exact matches first
    if event_lower in fallback_map:
        return fallback_map[event_lower]
    
    # Check for partial matches
    for key, date in fallback_map.items():
        if key in event_lower or any(word in event_lower for word in key.split()):
            return date

    return None

def send_email(to_email, subject, content):
    """Send email notification"""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        app.logger.warning("SMTP not configured - printing notification instead.")
        print(f"[MOCK EMAIL] To: {to_email}\nSubject: {subject}\n\n{content}\n")
        return True
    try:
        msg = EmailMessage()
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(content)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        app.logger.error("Failed to send email: %s", e)
        return False

def send_notification(reminder_id, reminder):
    """Send notification when reminder fires"""
    app.logger.info("Firing reminder %s for user %s", reminder_id, reminder.get("user_email"))
    to_email = reminder.get("user_email")
    subject = f"Reminder: {reminder.get('event_desc')}"
    content = (
        f"Hello,\n\nThis is your reminder for: {reminder.get('event_desc')}\n"
        f"Event date: {reminder.get('event_date')}\n\nMessage: {reminder.get('message')}\n\n"
        "— Your CampusCopilot Reminder Bot"
    )
    ok = send_email(to_email, subject, content)
    write_sent_log({
        "reminder_id": reminder_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sent": ok,
        "reminder": reminder
    })

def schedule_reminder(reminder):
    """Schedule a reminder job"""
    notify_time_str = reminder["notify_time"]
    notify_dt = dateparser.parse(notify_time_str)
    if notify_dt.tzinfo is None:
        notify_dt = notify_dt.replace(tzinfo=timezone.utc)
    
    job_id = f"reminder-{reminder['id']}"
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        pass
    
    scheduler.add_job(
        func=send_notification,
        trigger="date",
        run_date=notify_dt,
        args=[reminder["id"], reminder],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=60*60*24
    )
    app.logger.info("Scheduled reminder %s at %s (UTC)", reminder["id"], notify_dt.isoformat())

def reload_and_schedule_all():
    """Reload and reschedule all pending reminders"""
    reminders = load_reminders()
    for rem in reminders:
        try:
            notify_time = rem.get("notify_time")
            if not notify_time:
                continue
            ndt = dateparser.parse(notify_time)
            if ndt.tzinfo is None:
                ndt = ndt.replace(tzinfo=timezone.utc)
            if ndt > datetime.now(timezone.utc):
                schedule_reminder(rem)
        except Exception as e:
            app.logger.warning("Failed scheduling reminder from file: %s", e)


# -------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat_and_maybe_schedule():
    """Main chat endpoint that handles both Q&A and reminder requests"""
    data = request.get_json()
    user_id = str(data.get("user_id", "anonymous"))
    message = data.get("message", "")

    if not message:
        return jsonify({"error": "No query or message provided"}), 400

    app.logger.info(f"Processing message from user {user_id}: {message}")

    # Check if it's a reminder request
    is_reminder, event_description, offset_text = extract_reminder_info(message)
    
    if not is_reminder:
        # Handle normal Q&A
        if not llm_qa_chain:
            return jsonify({"error": "Q&A database not initialized"}), 500
        try:
            response = llm_qa_chain.invoke({"input": message})
            return jsonify({
                "intent": "normal",
                "answer": response["answer"]
            })
        except Exception as e:
            app.logger.error(f"Q&A processing error: {e}")
            return jsonify({"error": str(e)}), 500

    # Handle reminder request
    app.logger.info(f"Processing reminder - Event: {event_description}, Offset: {offset_text}")

    if not event_description or len(event_description.strip()) < 3:
        return jsonify({
            "error": "Please provide a clear event description for the reminder.",
            "example": "Remind me about exam 2 days before"
        }), 400

    user_email = DEFAULT_REMINDER_EMAIL
    
    # Resolve event date
    event_date_iso = resolve_event_date(event_description)
    app.logger.info(f"Resolved event date for '{event_description}': {event_date_iso}")
    
    if not event_date_iso:
        return jsonify({
            "error": f"Could not determine the date for '{event_description}'. Please provide a specific date or ensure the event exists in the college database.",
            "suggestion": "Try: 'Remind me about exam on 2025-05-15' or provide more context about the event."
        }), 400

    # Calculate notification time
    offset = parse_offset_text(offset_text)
    event_dt = dateparser.parse(event_date_iso)
    if event_dt.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=timezone.utc)
    notify_dt = event_dt - offset

    # Check if notification time is in the future
    current_time = datetime.now(timezone.utc)
    if notify_dt <= current_time:
        # If the notification time is in the past, but event is in the future,
        # adjust to notify immediately or give a helpful error
        if event_dt > current_time:
            # Event is in future but notification time has passed
            # Set notification for now + 1 minute
            notify_dt = current_time + timedelta(minutes=1)
            app.logger.info(f"Adjusted notification time to immediate: {notify_dt.isoformat()}")
        else:
            return jsonify({
                "error": "Both the event date and reminder time are in the past. Please provide a future event date.",
                "event_date": event_date_iso,
                "event_time": event_dt.isoformat(),
                "reminder_time": notify_dt.isoformat(),
                "current_time": current_time.isoformat()
            }), 400

    # Create and save reminder
    reminder_id = f"{user_id}-{int(datetime.now(timezone.utc).timestamp())}"
    reminder = {
        "id": reminder_id,
        "user_id": user_id,
        "user_email": user_email,
        "event_desc": event_description,
        "event_date": event_date_iso,
        "notify_time": notify_dt.isoformat(),
        "offset": str(offset),
        "message": f"Reminder for '{event_description}' scheduled {offset} before the event.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        append_reminder_to_file(reminder)
        schedule_reminder(reminder)
        
        app.logger.info(f"Successfully created reminder {reminder_id}")
        
        return jsonify({
            "status": "scheduled",
            "message": f"✅ Reminder set successfully!\n\nEvent: {event_description}\nDate: {event_date_iso}\nReminder: {offset} before event\nNotification time: {notify_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "reminder": {
                "id": reminder_id,
                "event": event_description,
                "event_date": event_date_iso,
                "reminder_time": notify_dt.isoformat()
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to create reminder: {e}")
        return jsonify({"error": "Failed to create reminder. Please try again."}), 500

@app.route("/reminders", methods=["GET"])
def list_reminders():
    """List all reminders"""
    try:
        reminders = load_reminders()
        # Filter future reminders
        current_time = datetime.now(timezone.utc)
        active_reminders = []
        
        for reminder in reminders:
            try:
                notify_time = dateparser.parse(reminder.get("notify_time"))
                if notify_time.tzinfo is None:
                    notify_time = notify_time.replace(tzinfo=timezone.utc)
                if notify_time > current_time:
                    active_reminders.append(reminder)
            except:
                continue
        
        return jsonify({
            "total": len(active_reminders),
            "reminders": active_reminders
        })
    except Exception as e:
        app.logger.error(f"Error listing reminders: {e}")
        return jsonify({"error": "Failed to load reminders"}), 500

@app.route("/cancel/<reminder_id>", methods=["POST"])
def cancel_reminder(reminder_id):
    """Cancel a specific reminder"""
    job_id = f"reminder-{reminder_id}"
    try:
        scheduler.remove_job(job_id)
        app.logger.info(f"Cancelled reminder {reminder_id}")
        return jsonify({"status": "cancelled", "reminder_id": reminder_id})
    except JobLookupError:
        return jsonify({
            "status": "not_found", 
            "message": "Reminder not found or already cancelled."
        }), 404
    except Exception as e:
        app.logger.error(f"Error cancelling reminder: {e}")
        return jsonify({"error": "Failed to cancel reminder"}), 500

@app.route("/api/status", methods=["GET"])
def get_status():
    """Get system status"""
    scheduled_jobs = len(scheduler.get_jobs())
    return jsonify({
        "system": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "active" if vectors else "offline",
        "scheduled_reminders": scheduled_jobs,
        "scheduler_running": scheduler.running
    })

@app.route("/test_date", methods=["POST"])
def test_date_resolution():
    """Test endpoint for date resolution functionality"""
    data = request.get_json()
    event_description = data.get("event_description", "")
    
    if not event_description:
        return jsonify({"error": "Please provide event_description"}), 400
    
    # Test the date resolution
    resolved_date = resolve_event_date(event_description)
    
    # Also test what the LLM returns
    llm_response = None
    if llm_qa_chain:
        try:
            response = llm_qa_chain.invoke({
                "input": f"What are the exact dates for {event_description}? Please provide the complete date range or specific dates."
            })
            llm_response = response.get("answer", "")
        except Exception as e:
            llm_response = f"Error: {str(e)}"
    
    return jsonify({
        "event_description": event_description,
        "resolved_date": resolved_date,
        "llm_raw_response": llm_response,
        "current_date": datetime.now().date().isoformat()
    })

@app.route("/test_reminder", methods=["POST"])
def test_reminder():
    """Test endpoint for reminder functionality"""
    data = request.get_json()
    message = data.get("message", "")
    
    is_reminder, event_desc, offset = extract_reminder_info(message)
    
    return jsonify({
        "is_reminder": is_reminder,
        "event_description": event_desc,
        "offset": offset,
        "parsed_offset": str(parse_offset_text(offset)) if offset else None
    })


if __name__ == "__main__":
    reload_and_schedule_all()
    print("🚀 Starting CampusCopilot server...")
    print(f"📧 Default reminder email: {DEFAULT_REMINDER_EMAIL}")
    print(f"📅 Scheduler running: {scheduler.running}")
    app.run(host="0.0.0.0", debug=True, port=5000)