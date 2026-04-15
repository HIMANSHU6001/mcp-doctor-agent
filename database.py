from __future__ import annotations

import os
from datetime import date as date_type
from datetime import datetime, time, timedelta
from typing import Any, Dict, List

from dotenv import load_dotenv
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

load_dotenv()

_raw_database_url = os.getenv("DATABASE_URL")
if not _raw_database_url:
    raise ValueError("DATABASE_URL is missing. Set it in the .env file.")

if _raw_database_url.startswith("postgresql://"):
    DATABASE_URL = _raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _raw_database_url

if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise ValueError("DATABASE_URL must start with 'postgresql+asyncpg://' for asyncpg support.")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    appointments: Mapped[List[Appointment]] = relationship(back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    symptoms: Mapped[str | None] = mapped_column(String(500), nullable=True)
    appointment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")


def _normalize_doctor_name(name: str) -> str:
    """Normalize doctor names to handle punctuation/spacing variants."""
    return " ".join(name.lower().replace(".", " ").split())


async def _resolve_doctor_by_name(session: AsyncSession, doctor_name: str) -> Doctor | None:
    """Resolve doctor name by exact match first, then normalized fallback."""
    exact_result = await session.execute(select(Doctor).where(Doctor.name == doctor_name))
    exact_doctor = exact_result.scalar_one_or_none()
    if exact_doctor is not None:
        return exact_doctor

    normalized_target = _normalize_doctor_name(doctor_name)
    all_doctors_result = await session.execute(select(Doctor))
    for doctor in all_doctors_result.scalars().all():
        if _normalize_doctor_name(doctor.name) == normalized_target:
            return doctor

    return None


def _build_daily_slots(target_date: date_type) -> List[datetime]:
    """Return hourly slots from 09:00 to 17:00 (inclusive)."""
    return [datetime.combine(target_date, time(hour=hour, minute=0)) for hour in range(9, 18)]


def _validate_booking_datetime(date_time: datetime) -> str | None:
    """Validate that appointment time is timezone-naive and within supported hourly slots."""
    if date_time.tzinfo is not None and date_time.tzinfo.utcoffset(date_time) is not None:
        return "Invalid appointment time. Please provide local time without timezone."

    if date_time.minute != 0 or date_time.second != 0 or date_time.microsecond != 0:
        return "Appointments must be booked on the hour (e.g., 09:00, 15:00)."

    valid_slots = _build_daily_slots(date_time.date())
    if date_time not in valid_slots:
        return "Appointments can only be booked between 09:00 and 17:00 on hourly slots."

    return None


async def get_daily_stats_db(date: str) -> Dict[str, Any]:
    """Return appointment analytics for a single day."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"ok": False, "message": "Invalid date format. Please use YYYY-MM-DD."}

    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as session:
        try:
            appointment_result = await session.execute(
                select(Appointment).where(
                    Appointment.appointment_date >= day_start,
                    Appointment.appointment_date < day_end,
                    Appointment.status == "scheduled",
                )
            )
            appointments = appointment_result.scalars().all()
        except SQLAlchemyError as exc:
            return {"ok": False, "message": f"Database error while fetching stats: {exc}"}

    fever_mentions = 0
    for appointment in appointments:
        searchable_text = " ".join(
            value for value in [appointment.symptoms, appointment.patient_name] if value
        ).lower()
        if "fever" in searchable_text:
            fever_mentions += 1

    return {
        "ok": True,
        "date": target_date.isoformat(),
        "appointment_count": len(appointments),
        "fever_mentions": fever_mentions,
    }


async def list_doctors_db() -> Dict[str, Any]:
    """Return all available doctors ordered by name."""
    async with AsyncSessionLocal() as session:
        try:
            doctors_result = await session.execute(select(Doctor).order_by(Doctor.name))
            doctors = doctors_result.scalars().all()
        except SQLAlchemyError as exc:
            return {
                "ok": False,
                "message": f"Database error while listing doctors: {exc}",
            }

    serialized = [
        {
            "id": doctor.id,
            "name": doctor.name,
        }
        for doctor in doctors
    ]
    return {
        "ok": True,
        "count": len(serialized),
        "doctors": serialized,
    }


async def get_or_create_doctor_by_email(doctor_email: str, doctor_name: str) -> Dict[str, Any]:
    """Ensure a doctor record exists for the provided email."""
    async with AsyncSessionLocal() as session:
        try:
            doctor_result = await session.execute(select(Doctor).where(Doctor.email == doctor_email))
            doctor = doctor_result.scalar_one_or_none()

            if doctor is None:
                doctor = Doctor(email=doctor_email, name=doctor_name)
                session.add(doctor)
                await session.commit()
                await session.refresh(doctor)
                return {
                    "ok": True,
                    "created": True,
                    "doctor": {
                        "id": doctor.id,
                        "name": doctor.name,
                        "email": doctor.email,
                    },
                }

            if doctor.name != doctor_name:
                doctor.name = doctor_name
                await session.commit()

            return {
                "ok": True,
                "created": False,
                "doctor": {
                    "id": doctor.id,
                    "name": doctor.name,
                    "email": doctor.email,
                },
            }
        except SQLAlchemyError as exc:
            await session.rollback()
            return {
                "ok": False,
                "message": f"Database error while syncing doctor profile: {exc}",
            }


async def get_doctor_contact_by_name_db(doctor_name: str) -> Dict[str, Any]:
    """Return doctor contact details by doctor name."""
    async with AsyncSessionLocal() as session:
        try:
            doctor = await _resolve_doctor_by_name(session=session, doctor_name=doctor_name)
            if doctor is None:
                return {
                    "ok": False,
                    "message": f"Doctor '{doctor_name}' not found.",
                }

            return {
                "ok": True,
                "doctor": {
                    "id": doctor.id,
                    "name": doctor.name,
                    "email": doctor.email,
                },
            }
        except SQLAlchemyError as exc:
            return {
                "ok": False,
                "message": f"Database error while fetching doctor contact: {exc}",
            }


async def init_db() -> None:
    """Create tables and insert an idempotent seed doctor."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Doctor).where(Doctor.email == "dr.ahuja@medagent.local")
            )
            doctor = result.scalar_one_or_none()
            if doctor is None:
                session.add(Doctor(name="Dr. Ahuja", email="dr.ahuja@medagent.local"))
                await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise


async def get_doctor_availability(doctor_name: str, date: str) -> str:
    """Return available hourly slots for a doctor on a given date (YYYY-MM-DD)."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD."

    async with AsyncSessionLocal() as session:
        try:
            doctor = await _resolve_doctor_by_name(session=session, doctor_name=doctor_name)
            if doctor is None:
                return f"Doctor '{doctor_name}' not found."

            day_start = datetime.combine(target_date, time.min)
            day_end = day_start + timedelta(days=1)

            appointment_result = await session.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor.id,
                    Appointment.appointment_date >= day_start,
                    Appointment.appointment_date < day_end,
                    Appointment.status == "scheduled",
                )
            )
            appointments = appointment_result.scalars().all()

            booked_slots = {
                appointment.appointment_date.replace(minute=0, second=0, microsecond=0)
                for appointment in appointments
            }

            available_slots = [
                slot for slot in _build_daily_slots(target_date) if slot not in booked_slots
            ]
            if not available_slots:
                return f"No available slots for {doctor.name} on {target_date.isoformat()}."

            formatted_slots = ", ".join(slot.strftime("%H:%M") for slot in available_slots)
            return (
                f"Available slots for {doctor.name} on {target_date.isoformat()}: {formatted_slots}"
            )
        except SQLAlchemyError as exc:
            return f"Database error while fetching availability: {exc}"


async def book_appointment_db(
    doctor_name: str,
    patient_name: str,
    date_time: datetime,
    symptoms: str | None = None,
) -> str:
    """Book an appointment if the slot is valid and still available."""
    async with AsyncSessionLocal() as session:
        try:
            doctor = await _resolve_doctor_by_name(session=session, doctor_name=doctor_name)
            if doctor is None:
                return f"Doctor '{doctor_name}' not found."

            validation_error = _validate_booking_datetime(date_time)
            if validation_error:
                return validation_error

            conflict_result = await session.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor.id,
                    Appointment.appointment_date == date_time,
                    Appointment.status == "scheduled",
                )
            )
            conflict = conflict_result.scalar_one_or_none()
            if conflict is not None:
                return (
                    f"Slot already booked for {doctor.name} at "
                    f"{date_time.strftime('%Y-%m-%d %H:%M')}."
                )

            appointment = Appointment(
                doctor_id=doctor.id,
                patient_name=patient_name,
                symptoms=symptoms,
                appointment_date=date_time,
                status="scheduled",
            )
            session.add(appointment)
            await session.commit()

            return (
                f"Appointment booked for {patient_name} with {doctor.name} on "
                f"{date_time.strftime('%Y-%m-%d %H:%M')}."
            )
        except SQLAlchemyError as exc:
            await session.rollback()
            return f"Database error while booking appointment: {exc}"