# models.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# =========================
# USER TABLE
# =========================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

    password_hash = db.Column(db.String(200), nullable=False)

    # user | doctor | admin
    role = db.Column(db.String(20), default="user")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    doctor_profile = db.relationship("Doctor", backref="user", uselist=False)
    bookings = db.relationship("Booking", backref="user", lazy=True)


# =========================
# DOCTOR TABLE
# =========================
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120))
    experience_years = db.Column(db.Integer, default=0)
    certificates = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    schedules = db.relationship("DoctorSchedule", backref="doctor", lazy=True)
    bookings = db.relationship("Booking", backref="doctor", lazy=True)


# =========================
# DOCTOR FREE SCHEDULE
# =========================
class DoctorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# BOOKING TABLE
# =========================
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    session_type = db.Column(db.String(20), default="offline")
    issue_description = db.Column(db.Text)

    # booked | ongoing | completed | cancelled
    status = db.Column(db.String(20), default="booked")

    cancel_reason = db.Column(db.Text)

    token_number = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    prescription = db.relationship("Prescription", backref="booking", uselist=False)


# =========================
# PRESCRIPTION TABLE
# =========================
class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)

    report_text = db.Column(db.Text)
    image_path = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# NOTIFICATION TABLE
# =========================
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200))
    message = db.Column(db.Text)

    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification_win(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
