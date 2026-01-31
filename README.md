# Chronex

A student productivity web application built with Flask — featuring task management, focus timer, notes, budget tracking, and gamification.

Artur Socolnic| University of Westminster | 6COSC022W

---

## Features

- **User Authentication** — Secure login/register with password hashing
- **Dashboard** — Daily overview with progress tracking
- **Task Management** — Create, edit, delete tasks with priorities and deadlines
- **Focus Timer** — Pomodoro-style timer with gamification rewards
- **Notes** — Quick note-taking for ideas and reminders
- **Budget Tracker** — Track income, expenses, and savings goals
- **Achievements** — 5 unlockable achievements to motivate productivity
- **Settings** — Profile management and account settings

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask |
| Database | SQLite, SQLAlchemy ORM |
| Frontend | HTML5, CSS3, JavaScript |
| Authentication | Flask-Login, Werkzeug |

---

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/chronex.git
cd chronex
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open in browser:
```
http://localhost:5000
```

---

## Demo Account

For testing purposes (Registration Feature is 
- **Username:** artur
- **Password:** 123

---

## Project Structure

```
chronex/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── run.bat               # Windows startup script
├── templates/            # HTML templates
│   ├── landing.html      # Landing/login page
│   ├── home.html         # Dashboard
│   ├── timetable.html    # Task management
│   ├── mynotes.html      # Notes
│   ├── focus.html        # Focus timer
│   ├── budget.html       # Budget tracker
│   ├── achievements.html # Achievements
│   └── settings.html     # User settings
├── static/
│   └── css/
│       └── style.css     # Stylesheet
└── instance/
    └── chronex_lite.db   # SQLite database (auto-generated)
```

---

## Author

University of Westminster  
Final Year Project 2025-2026
Artur Socolnic - Creator 

---

## License

This project is for academic purposes.
