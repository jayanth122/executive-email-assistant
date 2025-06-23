# main.py

import os
import json
import datetime
import smtplib
import pytz
import re
from dotenv import load_dotenv
from email.message import EmailMessage
from typing import Literal
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain.agents import initialize_agent, AgentType
from langchain.tools import tool

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# -----------------------
# 1. LOAD ENVIRONMENT
# -----------------------
load_dotenv()

SMTP_SERVER   = os.getenv("SMTP_SERVER")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 465))
SMTP_EMAIL    = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL")

CAL_SCOPES = [os.getenv("CAL_SCOPES")]
PROFILE_NAME = os.getenv("PROFILE_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")

# -----------------------
# 2. EMAIL TO PARSE (Example)
# -----------------------
email = {
    "author": "Lisa Patel <lisa.patel@example.com>",
    "to": "John Doe <doe474310@gmail.com>",
    "subject": "Free time on June 23?",
    "email_thread": (
        "Hi John,\n\n"
        "Could you let me know when you're free on June 23, 2025?\n"
        "I'd like to find a good time to catch up.\n\n"
        "Thanks,\n"
        "Lisa"
    )
}

# -----------------------
# 3. TRIAGE LOGIC
# -----------------------

TRIAGE_RULES = {
    "ignore": "Marketing newsletters, spam emails, mass announcements",
    "notify": "Team member out sick, notifications, project status",
    "respond": "Direct questions, meeting requests, critical bugs, availability"
}

triage_system_prompt = f"""
You are {PROFILE_NAME}'s executive assistant.
Classify each email into exactly one: ignore, notify, respond.

Rules:
- ignore: {TRIAGE_RULES['ignore']}
- notify: {TRIAGE_RULES['notify']}
- respond: {TRIAGE_RULES['respond']}

Return exactly JSON:
{{"reasoning": string, "classification": "ignore"|"notify"|"respond"}}
"""

user_prompt_template = """From: {author}
To: {to}
Subject: {subject}

{email_thread}
"""

class Router(BaseModel):
    reasoning: str
    classification: Literal["ignore", "notify", "respond"]

def classify_email_with_llm(llm, system, user):
    resp = llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]).content.strip()

    try:
        parsed = json.loads(resp)
    except json.JSONDecodeError:
        classification_match = re.search(r'"?(respond|notify|ignore)"?', resp)
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', resp)

        if classification_match:
            classification = classification_match.group(1)
            reasoning = reasoning_match.group(1) if reasoning_match else "No detailed reasoning provided"
            parsed = {
                "reasoning": reasoning,
                "classification": classification
            }
        else:
            raise ValueError(f"Failed to parse classification:\n{resp}")

    return Router(**parsed)

# -----------------------
# 4. TOOL DEFINITIONS
# -----------------------

@tool(description="Write and send an email. Expects 'body' and 'subject'")
def write_email(subject: str, body: str) -> str:
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = MANAGER_EMAIL
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        return f"✉️ Email sent to {MANAGER_EMAIL} with subject '{subject}'"
    except Exception as e:
        return f"❌ Failed to send email: {e}"

@tool(description="Schedule a meeting. Expects 'subject', 'duration_minutes', and 'day' (YYYY-MM-DD).")
def schedule_meeting(subject: str, duration: int, day: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", day)
    if not match:
        return "❌ Invalid date format"
    day = match.group(0)

    attendees = [MANAGER_EMAIL]
    timezone = 'Canada/Eastern'
    est = pytz.timezone(timezone)
    start_datetime = est.localize(datetime.datetime.strptime(day + " 10:00", "%Y-%m-%d %H:%M"))
    end_datetime = start_datetime + datetime.timedelta(minutes=duration)

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', CAL_SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_SECRET_FILE, CAL_SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as tk:
            tk.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': subject,
        'start': {'dateTime': start_datetime.isoformat(), 'timeZone': timezone},
        'end': {'dateTime': end_datetime.isoformat(), 'timeZone': timezone},
        'attendees': attendees
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    if os.path.exists("token.json"):
        os.remove("token.json")

    return f"✅ Event created: {created_event.get('htmlLink')}"

@tool(description="Check calendar availability for a day (YYYY-MM-DD).")
def check_calendar_availability(day: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", day)
    if not match:
        return "❌ Invalid date format"
    day = match.group(0)
    eastern = pytz.timezone("Canada/Eastern")

    day_date = datetime.date.fromisoformat(day)
    tmin = eastern.localize(datetime.datetime.combine(day_date, datetime.time.min)).astimezone(pytz.utc).isoformat()
    tmax = eastern.localize(datetime.datetime.combine(day_date, datetime.time.max)).astimezone(pytz.utc).isoformat()

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', CAL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_SECRET_FILE, CAL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as tk:
            tk.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    body = {
        'timeMin': tmin,
        'timeMax': tmax,
        'items': [{'id': 'primary'}],
        'timeZone': 'Canada/Eastern'
    }
    busy = service.freebusy().query(body=body).execute()['calendars']['primary']['busy']

    frees = []
    last_end = eastern.localize(datetime.datetime.combine(day_date, datetime.time(9)))

    for slot in busy:
        bs = datetime.datetime.fromisoformat(slot['start']).astimezone(eastern)
        be = datetime.datetime.fromisoformat(slot['end']).astimezone(eastern)

        if bs > last_end:
            frees.append(f"{last_end.time().strftime('%H:%M')}–{bs.time().strftime('%H:%M')}")
        last_end = max(last_end, be)

    eod = eastern.localize(datetime.datetime.combine(day_date, datetime.time(17)))
    if last_end < eod:
        frees.append(f"{last_end.time().strftime('%H:%M')}–17:00")
    
    if os.path.exists("token.json"):
        os.remove("token.json")

    return f"Free slots on {day} (EST): {', '.join(frees) if frees else 'No free slots'}."

# -----------------------
# 5. AGENT SYSTEM PROMPT
# -----------------------

agent_system_prompt = f"""
You are {PROFILE_NAME}'s executive assistant.

Your job is to help John handle his emails by picking the right tool to take action.

TOOLS:

1. write_email:
- Use when John needs to be informed about the content of the email.
- This sends a summary to John — NOT a reply to the sender.

Format:
{{
  "action": "write_email",
  "action_input": {{
    "subject": "A short subject",
    "body": "A summary of the email for John"
  }}
}}

2. schedule_meeting:
Use this when someone wants to book a time.
Format:
{{
  "action": "schedule_meeting",
  "action_input": {{
    "subject": "Meeting title",
    "duration": 30,
    "day": "2025-06-24"
  }}
}}

3. check_calendar_availability:
When someone asks when John is free.
Format:
{{
  "action": "check_calendar_availability",
  "action_input": {{
    "day": "2025-06-23"
  }}
}}

Always return a single valid JSON with the correct fields.
"""

# -----------------------
# 6. MAIN FLOW
# -----------------------

def main():
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama3-70b-8192",
        temperature=0.0
    )

    agent = initialize_agent(
        tools=[write_email, schedule_meeting, check_calendar_availability],
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        max_iterations=2,
        early_stopping_method="force",
        prefix=agent_system_prompt,
        handle_parsing_errors=True,
    )

    user_prompt = user_prompt_template.format(**email)
    result = classify_email_with_llm(llm, triage_system_prompt, user_prompt)

    print(f"🧠 Classification: {result.classification}")
    print(f"🧠 Reasoning: {result.reasoning}")

    if result.classification == "respond":
        agent_result = agent.invoke({"input": user_prompt})
        print("🤖 Agent Output:\n", agent_result["output"])
    elif result.classification == "notify":
        print("🔔 Notify: This is important but no reply needed.")
    else:
        print("🚫 Ignore: No action taken.")

if __name__ == "__main__":
    main()
