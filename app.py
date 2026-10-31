import csv
import io
import os
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, g, make_response, redirect, render_template,
    request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "attendance.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','employee')) DEFAULT 'employee',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        work_date TEXT NOT NULL,
        check_in TEXT,
        check_out TEXT,
        status TEXT NOT NULL DEFAULT 'present'
            CHECK(status IN ('present','absent','half_day','on_leave')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, work_date)
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','approved','rejected')),
        reviewed_by INTEGER REFERENCES users(id),
        reviewed_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(work_date);
    CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status);
    """)
    conn.commit()
    conn.close()


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("_csrf_token")
        submitted = request.form.get("_csrf_token")
        if not token or not submitted or not secrets.compare_digest(token, submitted):
            abort(400, description="Invalid or missing security token. Refresh the page and try again.")


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]
    return {"csrf_token": csrf_token}


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user and user["is_active"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["email"] = user["email"]
            session["_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"))
        flash("Invalid email/password, or this account is inactive.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    if session["role"] == "admin":
        stats = {
            "employees": db.execute(
                "SELECT COUNT(*) FROM users WHERE role='employee' AND is_active=1"
            ).fetchone()[0],
            "present": db.execute(
                "SELECT COUNT(*) FROM attendance WHERE work_date=? AND check_in IS NOT NULL",
                (today,)
            ).fetchone()[0],
            "pending": db.execute(
                "SELECT COUNT(*) FROM leave_requests WHERE status='pending'"
            ).fetchone()[0],
        }
        recent = db.execute("""
            SELECT a.work_date, a.check_in, a.check_out, a.status, u.name
            FROM attendance a JOIN users u ON u.id=a.user_id
            ORDER BY a.work_date DESC, a.id DESC LIMIT 10
        """).fetchall()
        return render_template("dashboard.html", today=today, stats=stats, recent=recent)

    attendance = db.execute(
        "SELECT * FROM attendance WHERE user_id=? AND work_date=?",
        (session["user_id"], today)
    ).fetchone()
    history = db.execute("""
        SELECT work_date, check_in, check_out, status FROM attendance
        WHERE user_id=? ORDER BY work_date DESC LIMIT 10
    """, (session["user_id"],)).fetchall()
    leaves = db.execute("""
        SELECT start_date, end_date, reason, status FROM leave_requests
        WHERE user_id=? ORDER BY id DESC LIMIT 5
    """, (session["user_id"],)).fetchall()
    return render_template("dashboard.html", today=today, attendance=attendance,
                           history=history, leaves=leaves)


@app.route("/attendance/check-in", methods=["POST"])
@login_required
def check_in():
    if session["role"] != "employee":
        abort(403)
    db = get_db()
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = db.execute(
        "SELECT * FROM attendance WHERE user_id=? AND work_date=?",
        (session["user_id"], today)
    ).fetchone()
    if row and row["check_in"]:
        flash("You have already checked in today.", "error")
    elif row:
        db.execute("UPDATE attendance SET check_in=?, status='present' WHERE id=?",
                   (now, row["id"]))
        db.commit()
        flash("Check-in recorded.", "success")
    else:
        db.execute(
            "INSERT INTO attendance(user_id,work_date,check_in,status) VALUES(?,?,?,'present')",
            (session["user_id"], today, now)
        )
        db.commit()
        flash("Check-in recorded.", "success")
    return redirect(url_for("dashboard"))


@app.route("/attendance/check-out", methods=["POST"])
@login_required
def check_out():
    if session["role"] != "employee":
        abort(403)
    db = get_db()
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = db.execute(
        "SELECT * FROM attendance WHERE user_id=? AND work_date=?",
        (session["user_id"], today)
    ).fetchone()
    if not row or not row["check_in"]:
        flash("Please check in before checking out.", "error")
    elif row["check_out"]:
        flash("You have already checked out today.", "error")
    else:
        db.execute("UPDATE attendance SET check_out=? WHERE id=?", (now, row["id"]))
        db.commit()
        flash("Check-out recorded.", "success")
    return redirect(url_for("dashboard"))


@app.route("/attendance")
@login_required
def attendance_history():
    db = get_db()
    if session["role"] == "admin":
        records = db.execute("""
            SELECT a.work_date,a.check_in,a.check_out,a.status,u.name,u.email
            FROM attendance a JOIN users u ON u.id=a.user_id
            ORDER BY a.work_date DESC,u.name LIMIT 1000
        """).fetchall()
    else:
        records = db.execute("""
            SELECT work_date,check_in,check_out,status,NULL AS name,NULL AS email
            FROM attendance WHERE user_id=? ORDER BY work_date DESC LIMIT 200
        """, (session["user_id"],)).fetchall()
    return render_template("attendance.html", records=records)


@app.route("/employees", methods=["GET", "POST"])
@admin_required
def employees():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "employee")
        if not name or "@" not in email or len(password) < 10 or role not in ("admin", "employee"):
            flash("Enter a name, valid email, password (at least 10 characters), and role.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                    (name, email, generate_password_hash(password), role)
                )
                db.commit()
                flash("Account created.", "success")
                return redirect(url_for("employees"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email is already registered.", "error")
    rows = db.execute(
        "SELECT id,name,email,role,is_active,created_at FROM users ORDER BY id DESC"
    ).fetchall()
    return render_template("employees.html", employees=rows)


@app.route("/employees/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_employee(user_id):
    if user_id == session["user_id"]:
        flash("You cannot deactivate your own account.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
                   (user_id,))
        db.commit()
        flash("Account status updated.", "success")
    return redirect(url_for("employees"))


@app.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    db = get_db()
    if request.method == "POST":
        if session["role"] != "employee":
            abort(403)
        start = request.form.get("start_date", "")
        end = request.form.get("end_date", "")
        reason = request.form.get("reason", "").strip()
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
            if start_date < date.today() or end_date < start_date or not reason:
                raise ValueError
            db.execute(
                "INSERT INTO leave_requests(user_id,start_date,end_date,reason,status) VALUES(?,?,?,?,'pending')",
                (session["user_id"], start, end, reason)
            )
            db.commit()
            flash("Leave request submitted for approval.", "success")
            return redirect(url_for("leave"))
        except ValueError:
            flash("Use valid dates (today or later), ensure the end date is not before the start date, and enter a reason.", "error")
    if session["role"] == "admin":
        requests = db.execute("""
            SELECT l.id,l.start_date,l.end_date,l.reason,l.status,l.created_at,u.name,u.email
            FROM leave_requests l JOIN users u ON u.id=l.user_id
            ORDER BY CASE WHEN l.status='pending' THEN 0 ELSE 1 END,l.created_at DESC
        """).fetchall()
        return render_template("admin_leaves.html", requests=requests)
    requests = db.execute("""
        SELECT id,start_date,end_date,reason,status,created_at FROM leave_requests
        WHERE user_id=? ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()
    return render_template("leave.html", requests=requests, today=date.today().isoformat())


@app.route("/leave/<int:request_id>/review", methods=["POST"])
@admin_required
def review_leave(request_id):
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected"):
        abort(400)
    db = get_db()
    row = db.execute("SELECT status FROM leave_requests WHERE id=?", (request_id,)).fetchone()
    if not row:
        abort(404)
    if row["status"] != "pending":
        flash("This request has already been reviewed.", "error")
    else:
        db.execute("""
            UPDATE leave_requests SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'
        """, (decision, session["user_id"], request_id))
        db.commit()
        flash(f"Leave request {decision}.", "success")
    return redirect(url_for("leave"))


@app.route("/reports/attendance.csv")
@admin_required
def attendance_csv():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    db = get_db()
    sql = """SELECT u.name,u.email,a.work_date,a.check_in,a.check_out,a.status
             FROM attendance a JOIN users u ON u.id=a.user_id"""
    params = []
    if start or end:
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
            if end_date < start_date:
                raise ValueError
        except ValueError:
            abort(400, description="Provide valid start and end dates.")
        sql += " WHERE a.work_date BETWEEN ? AND ?"
        params.extend([start, end])
    sql += " ORDER BY a.work_date DESC,u.name"
    records = db.execute(sql, params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee", "Email", "Work Date", "Check In", "Check Out", "Status"])
    for row in records:
        writer.writerow([row["name"], row["email"], row["work_date"],
                         row["check_in"], row["check_out"], row["status"]])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=attendance-report.csv"
    return response


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403,
                           message="You do not have permission to access this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404,
                           message="The requested page was not found."), 404


@app.errorhandler(400)
def bad_request(error):
    message = getattr(error, "description", "Bad request.")
    return render_template("error.html", code=400, message=message), 400


if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="127.0.0.1", port=5000)
