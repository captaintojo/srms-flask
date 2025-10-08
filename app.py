import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "database.db"

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(\"\"\"
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','student')),
        student_id INTEGER
    )
    \"\"\")
    c.execute(\"\"\"
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT,
        dob TEXT
    )
    \"\"\")
    c.execute(\"\"\"
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course TEXT NOT NULL,
        score INTEGER NOT NULL,
        grade TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    \"\"\")
    conn.commit()

    # create default admin if not exists
    c.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        hashed = generate_password_hash("admin123")
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", hashed, "admin"))
        conn.commit()
    conn.close()

@app.before_first_request
def setup():
    init_db()

@app.route("/")
def index():
    if session.get("role") == "admin":
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("dashboard"))
            else:
                return "Student view not implemented in this demo."
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def admin_required():
    if session.get("role") != "admin":
        flash("Admin access required", "danger")
        return False
    return True

@app.route("/dashboard")
def dashboard():
    if not admin_required():
        return redirect(url_for("login"))
    db = get_db()
    students = db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    return render_template("dashboard.html", students=students)

@app.route("/student/add", methods=["GET","POST"])
def add_student():
    if not admin_required():
        return redirect(url_for("login"))
    if request.method == "POST":
        reg_no = request.form["reg_no"].strip()
        name = request.form["name"].strip()
        department = request.form["department"].strip()
        dob = request.form["dob"].strip()
        db = get_db()
        try:
            cur = db.cursor()
            cur.execute("INSERT INTO students (reg_no, name, department, dob) VALUES (?, ?, ?, ?)",
                        (reg_no, name, department, dob))
            student_id = cur.lastrowid
            pw = generate_password_hash(reg_no)
            cur.execute("INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
                        (reg_no, pw, "student", student_id))
            db.commit()
            flash("Student added successfully.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("Registration number already exists.", "danger")
    return render_template("add_student.html")

@app.route("/student/<int:sid>/view")
def view_results(sid):
    if not admin_required():
        return redirect(url_for("login"))
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("dashboard"))
    results = db.execute("SELECT * FROM results WHERE student_id = ?", (sid,)).fetchall()
    return render_template("view_results.html", student=student, results=results)

@app.route("/result/add/<int:sid>", methods=["POST"])
def add_result(sid):
    if not admin_required():
        return redirect(url_for("login"))
    course = request.form.get("course","").strip()
    score = request.form.get("score","").strip()
    try:
        score_int = int(score)
    except:
        flash("Score must be a number", "danger")
        return redirect(url_for("view_results", sid=sid))
    grade = "F"
    if score_int >= 70:
        grade = "A"
    elif score_int >= 60:
        grade = "B"
    elif score_int >= 50:
        grade = "C"
    elif score_int >= 40:
        grade = "D"
    db = get_db()
    db.execute("INSERT INTO results (student_id, course, score, grade) VALUES (?, ?, ?, ?)",
               (sid, course, score_int, grade))
    db.commit()
    flash("Result added", "success")
    return redirect(url_for("view_results", sid=sid))

if __name__ == "__main__":
    app.run(debug=True)