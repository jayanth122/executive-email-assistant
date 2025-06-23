# Executive Email Assistant

An AI-powered assistant that reads, classifies, and responds to emails — with automated scheduling and calendar integration. Built using **LangChain**, **Google Calendar API**, and **LLMs**, it intelligently triages emails and takes contextual actions like:

- 📨 Summarizing and notifying important emails
- 📅 Scheduling meetings
- 📆 Checking availability on your calendar

---

## 🚀 Features

- **Smart Email Triage**  
  Uses LLM (LLaMA3 via Groq) to classify emails as:
  - ignore: newsletters, spam, bulk
  - notify: updates, out-of-office, FYIs
  - respond: meeting requests, critical actions, direct questions

- **LLM Agent Action Router**  
  Automatically decides which tool to invoke:
  - Schedule meetings via Google Calendar
  - Check calendar availability
  - Send summary emails to the user

- **Secure Configuration via `.env`**
  All credentials are stored outside of the code.

## 🛠️ Setup Instructions

### 1. Clone the Repository

git clone https://github.com/yourusername/executive-email-assistant.git
cd executive-email-assistant

### 2. Set Up a Virtual Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

### 3. Install Dependencies
pip install -r requirements.txt
If requirements.txt is missing, you can generate it with:

pip freeze > requirements.txt

### 4. 🔑 Google Calendar API Setup
Go to Google Cloud Console

Create a new project

Enable Google Calendar API

Create OAuth 2.0 Client ID credentials (Application type: Desktop)

Download the credentials.json and place it in your project root

On first run, the app will prompt for Google login and generate token.json

### 🧪 Usage
Run the assistant with:
python main.py
The app will:

Classify the sample email (in main.py)

Decide on the appropriate action

Execute the action (e.g., check availability, schedule meeting, or send summary)

### How It Works
Email Classification Logic
Classification	Triggers	Example Use Case
ignore	None	Newsletters, spam, marketing emails
notify	Print notification	"I'm out sick today", status updates
respond	Triggers LLM agent	Meeting requests, availability inquiries

Agent Tools Available
write_email – Sends a summary email to the manager

check_calendar_availability – Checks your Google Calendar for free time

schedule_meeting – Schedules an event via Calendar API

