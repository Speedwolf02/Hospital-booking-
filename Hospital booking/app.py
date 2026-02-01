from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import dateparser

from config import Config
from models import (
    db, User, Doctor, DoctorSchedule,
    Booking, Prescription, Notification, Notification_win
)

# offline AI
from whisper_stt_processor import transcribe_audio_whisper
from tinyllama_client import tinyllama_chat
from tts_engine import synthesize_to_wav

# =========================
# APP INIT
# =========================
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# AUTO BOOKING STATUS UPDATE
# =========================
def update_booking_status():
    now = datetime.now()

    # booked → ongoing
    booked = Booking.query.filter(
        Booking.status == "booked",
        Booking.start_time <= now,
        Booking.end_time > now
    ).all()

    for b in booked:
        b.status = "ongoing"

    # ongoing → completed
    completed = Booking.query.filter(
        Booking.status.in_(["booked", "ongoing"]),
        Booking.end_time <= now
    ).all()

    for b in completed:
        b.status = "completed"

    db.session.commit()


# =========================
# HOME
# =========================
@app.route("/")
def index():
    return render_template("index.html")


# =========================
# AUTH
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            username=request.form["username"].strip(),
            email=request.form["email"].strip(),
            phone=request.form["phone"],
            address=request.form["address"],
            password_hash=generate_password_hash(request.form["password"]),
            role="user"   # force user
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("user_dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            username=request.form["username"]
        ).first()

        if not user or not check_password_hash(
            user.password_hash,
            request.form["password"]
        ):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

        login_user(user)

        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        if user.role == "doctor":
            return redirect(url_for("doctor_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# =========================
# USER DASHBOARD
# =========================
@app.route("/user/dashboard")
@login_required
def user_dashboard():
    if current_user.role != "user":
        return redirect("/")

    update_booking_status()

    doctors = Doctor.query.all()
    
    bookings = Booking.query.filter_by(
        user_id=current_user.id
    ).order_by(Booking.start_time.desc()).all()

    # --- NEW CODE: Fetch Notifications ---
    # Ensure you have imported the Notification model
    notifications = Notification_win.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).all()

    return render_template(
        "user_dashboard.html",
        doctors=doctors,
        bookings=bookings,
        notifications=notifications  # <--- PASS THIS TO HTML
    )

@app.route("/api/notifications/mark_read", methods=["POST"])
@login_required
def mark_notifications_read():
    # Find all unread notifications for this user
    unread_notifs = Notification_win.query.filter_by(user_id=current_user.id, is_read=False).all()
    
    for n in unread_notifs:
        n.is_read = True  # Mark as read
    
    db.session.commit()
    return jsonify(success=True)
# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return redirect("/")

    update_booking_status()

    return render_template(
        "admin_dashboard.html",
        doctors=Doctor.query.all(),
        users=User.query.all(),
        bookings=Booking.query.order_by(Booking.start_time.desc()).all()
    )


# =========================
# ADMIN ADD DOCTOR
# =========================
@app.route("/api/admin/doctor/add", methods=["POST"])
@login_required
def admin_add_doctor():
    if current_user.role != "admin":
        return jsonify(success=False), 403

    data = request.json

    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        role="doctor"
    )
    db.session.add(user)
    db.session.flush()

    doctor = Doctor(
        user_id=user.id,
        name=data["name"],
        department=data["department"],
        experience_years=int(data["experience"]),
        certificates=data["certificate"]
    )
    db.session.add(doctor)
    db.session.commit()

    return jsonify(success=True, message="Doctor added")


# =========================
# DOCTOR DASHBOARD
# =========================
@app.route("/doctor/dashboard")
@login_required
def doctor_dashboard():
    # 1. Check Role
    if current_user.role != "doctor":
        return redirect("/")

    # 2. Update status of old bookings (optional helper function)
    update_booking_status()

    # 3. Get the current Doctor profile
    doctor = Doctor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    # 4. Get bookings for THIS doctor
    bookings = Booking.query.filter_by(
        doctor_id=doctor.id
    ).order_by(Booking.start_time).all()

    # 5. --- NEW: Get ALL doctors for the Transfer Popup ---
    all_doctors = Doctor.query.all()

    return render_template(
        "doctor_dashboard.html",
        doctor=doctor,
        bookings=bookings,
        all_doctors=all_doctors  # <--- Pass this to the HTML!
    )

# =========================
# DOCTOR ADD FREE SCHEDULE
# =========================
@app.route("/api/doctor/add_schedule", methods=["POST"])
@login_required
def doctor_add_schedule():
    if current_user.role != "doctor":
        return jsonify(success=False), 403

    doctor = Doctor.query.filter_by(
        user_id=current_user.id
    ).first()

    data = request.json
    start = datetime.fromisoformat(data["start_time"])
    end = datetime.fromisoformat(data["end_time"])

    if end <= start:
        return jsonify(success=False, message="Invalid time")

    db.session.add(
        DoctorSchedule(
            doctor_id=doctor.id,
            start_time=start,
            end_time=end
        )
    )
    db.session.commit()

    return jsonify(success=True, message="Schedule added")


# =========================
# SLOT CHECK
# =========================
@app.route("/api/check_slot", methods=["POST"])
@login_required
def check_slot():
    data = request.json

    start = datetime.strptime(
        data["booking_time"], "%Y-%m-%d %H:%M"
    )
    end = start + timedelta(minutes=30)

    free = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == int(data["doctor_id"]),
        DoctorSchedule.start_time <= start,
        DoctorSchedule.end_time >= end
    ).first()

    if not free:
        return jsonify(available=False, reason="Doctor not available")

    clash = Booking.query.filter(
        Booking.doctor_id == int(data["doctor_id"]),
        Booking.status.in_(["booked", "ongoing"]),
        Booking.start_time < end,
        Booking.end_time > start
    ).first()

    if clash:
        return jsonify(available=False, reason="Already booked")

    return jsonify(available=True)


# =========================
# BOOK APPOINTMENT
# =========================
@app.route("/api/book", methods=["POST"])
@login_required
def api_book():
    data = request.json or {}

    try:
        start_time = datetime.strptime(data["booking_time"], "%Y-%m-%d %H:%M")
    except Exception:
        return jsonify({"success": False, "message": "Invalid booking time"})

    end_time = start_time + timedelta(minutes=30)
    doctor_id = int(data["doctor_id"])

    # 🔒 RECHECK FREE SCHEDULE
    free = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.start_time <= start_time,
        DoctorSchedule.end_time >= end_time
    ).first()

    if not free:
        return jsonify({
            "success": False,
            "message": "Doctor not available at that time"
        })

    # 🔒 RECHECK CONFLICT
    conflict = Booking.query.filter(
        Booking.doctor_id == doctor_id,
        Booking.status == "booked",
        Booking.start_time < end_time,
        Booking.end_time > start_time
    ).first()

    if conflict:
        return jsonify({
            "success": False,
            "message": "Slot already booked"
        })

    booking = Booking(
        user_id=current_user.id,
        doctor_id=doctor_id,
        start_time=start_time,
        end_time=end_time,
        issue_description=data.get("issue_description", ""),
        session_type=data.get("session_type", "offline"),
        status="booked"
    )

    db.session.add(booking)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Booking confirmed successfully"
    })



# =========================
# USER and Doctor CANCEL BOOKING
# =========================
@app.route("/api/booking/<int:bid>/cancel", methods=["POST"])
@login_required
def cancel_booking(bid):
    booking = Booking.query.get_or_404(bid)

    if booking.user_id != current_user.id:
        abort(403)

    booking.status = "cancelled"
    booking.cancel_reason = request.json["reason"]

    db.session.add(Notification(
        user_id=booking.user_id,
        title="Booking Cancelled",
        message=booking.cancel_reason
    ))
    db.session.commit()

    return jsonify(success=True)


@app.route("/api/doctor/booking/<int:booking_id>/cancel", methods=["POST"])
def doctor_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json()
    reason = data.get("reason", "No reason provided")

    # Update the booking status
    booking.status = "cancelled"
    booking.cancel_reason = reason  # Ensure your Database Model has this column
    
    db.session.commit()
    return jsonify(success=True, message=f"Booking cancelled: {reason}")

# =========================
# Transfer Doctor Booking
# =========================


# Update your transfer route
@app.route("/api/doctor/booking/<int:booking_id>/transfer", methods=["POST"])
def transfer_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    old_doctor_name = booking.doctor.name # Get current doctor's name
    new_doc_id = request.json.get("new_doctor_id")
    
    new_doctor = Doctor.query.get(new_doc_id)
    booking.doctor_id = new_doc_id
    
    # Create notification for the user
    msg = f"1 booking transferred from Dr. {old_doctor_name} to Dr. {new_doctor.name}."
    new_notif = Notification_win(user_id=booking.user_id, message=msg)
    
    db.session.add(new_notif)
    db.session.commit()
    return jsonify(success=True, message="Transferred successfully")


# =========================
# STT (WHISPER)
# =========================

@app.route("/api/stt/whisper", methods=["POST"])
def api_stt_whisper():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    f = request.files["audio"]

    save_dir = os.path.join(Config.UPLOAD_FOLDER)
    os.makedirs(save_dir, exist_ok=True)

    audio_path = os.path.join(save_dir, "recording.wav")
    f.save(audio_path)

    text, success = transcribe_audio_whisper(audio_path)

    if not success:
        return jsonify({"error": text}), 500

    return jsonify({"text": text})


# =========================
# TTS
# =========================
@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text"}), 400
    filename = synthesize_to_wav(text)
    audio_url = url_for("static", filename=f"tts/{filename}")
    return jsonify({"audio_url": audio_url})


# =========================
# AI CHAT
# =========================
@app.route("/api/tinyllama/assistant", methods=["POST"])
def tinyllama_api():
    reply = tinyllama_chat(
        "You are a hospital assistant.",
        request.json["message"]
    )
    return jsonify(reply=reply)


# =========================
# PARSE DATE
# =========================
@app.route("/api/parse_booking_time", methods=["POST"])
@login_required
def parse_time():
    dt = dateparser.parse(
        request.json["spoken"],
        settings={"PREFER_DATES_FROM": "future"}
    )
    if not dt:
        return jsonify(ok=False)

    return jsonify(ok=True, iso=dt.strftime("%Y-%m-%d %H:%M"))

@app.route("/api/upload_scan_prescription", methods=["POST"])
@login_required
def upload_scan_prescription():
    if 'prescription' not in request.files:
        return jsonify(success=False, message="No file uploaded")
    
    file = request.files['prescription']
    booking_id = request.form.get('booking_id')
    
    # Save the file
    filename = f"presc_{booking_id}_{file.filename}"
    filepath = os.path.join("static/uploads/prescriptions", filename)
    file.save(filepath)

    # 1. Extract text from image (Using OCR)
    # Placeholder: extracted_text = ocr_tool.extract(filepath)
    extracted_text = "Patient requires Amoxicillin 500mg twice a day for 5 days." 

    # 2. Send extracted text to TinyLlama for "Scanning" / Analysis
    prompt = f"Summarize and explain this medical prescription text clearly: {extracted_text}"
    ai_analysis = tinyllama_chat("You are a medical assistant analyzer.", prompt)

    # 3. Save record to DB
    new_presc = Prescription(booking_id=booking_id, image_path=filepath)
    db.session.add(new_presc)
    db.session.commit()

    return jsonify(success=True, analysis=ai_analysis)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                email="admin@hospital.com",
                password_hash=generate_password_hash("admin123"),
                role="admin"
            ))
            db.session.commit()

    app.run(debug=True)
