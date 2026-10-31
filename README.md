# StaffTrack — Employee Attendance & Leave Management System

A beginner-friendly Flask + SQLite portfolio application.

## Features
- Admin and employee roles
- Secure password hashes
- Admin creates/deactivates user accounts
- Employee check-in/check-out and personal attendance history
- Leave requests with admin approval/rejection
- Admin CSV attendance export, optional date range
- SQLite database file created automatically
- CSRF token checks on POST forms and basic security headers

## Requirements
- Python 3.10 or newer recommended
- VS Code (optional)

## Windows setup (PowerShell)
1. Extract this folder and open it in VS Code.
2. Open Terminal → New Terminal.
3. Create and activate the virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead:
```bat
.venv\Scripts\activate.bat
```

4. Install dependencies:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Set a secret key for the current PowerShell terminal:
```powershell
$env:FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

6. Create the first admin account:
```powershell
python create_admin.py
```
Enter a name, email, and password of at least 10 characters. The password is not stored in plaintext.

7. Start the app:
```powershell
python app.py
```

8. Open `http://127.0.0.1:5000` in your browser and sign in with the admin account.

## macOS / Linux setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python create_admin.py
python app.py
```
Open `http://127.0.0.1:5000`.

## How to use
1. Sign in as admin.
2. Open Employees and create an employee account.
3. Log out; sign in with that employee account.
4. Click Check in and later Check out.
5. Submit a leave request.
6. Log in as admin, open Leave, and approve or reject the request.
7. As admin, open CSV Report or Attendance → Export CSV.

CSV URL:
`http://127.0.0.1:5000/reports/attendance.csv`

Optional date range:
`/reports/attendance.csv?start=2026-10-01&end=2026-10-31`

## Database
`attendance.db` is created in the project folder on first initialization. Do not delete this file if you want to keep the data. Back it up before updates.

## AWS deployment later
SQLite is suitable for local learning and a single-instance demo. For a real multi-user production deployment, use a managed database such as Amazon RDS for MySQL, HTTPS, a production WSGI server such as Gunicorn, reverse proxy, managed secrets, backups, monitoring, and a thorough security review.

## Important limitations
This is an educational starter, not a fully audited HR application. Before real company use, add MFA and login rate limiting, audit logs, a documented business timezone, retention rules, automated backups, and further security testing. Admin account creation is done through the local command-line script rather than a public registration page.

## Design notes
Modern light/dark theme: sidebar navigation with icons (bottom tab bar on phones), gradient hero with a live clock and an 8-hour progress ring on the employee dashboard, avatar initials and status pills in tables. Styles are in `static/style.css` (colours are variables at the top, with a separate dark palette); behaviour is in `static/app.js` (live clock, greeting, theme toggle; no dependencies). The font (Plus Jakarta Sans) loads from Google Fonts and falls back to system fonts offline.
