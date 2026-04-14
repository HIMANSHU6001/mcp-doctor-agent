from __future__ import annotations

import os
from datetime import date as date_type
from datetime import datetime, time, timedelta
from typing import List

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
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    specialty: Mapped[str] = mapped_column(String(255), nullable=False)

    appointments: Mapped[List[Appointment]] = relationship(back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    appointment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")


def _build_daily_slots(target_date: date_type) -> List[datetime]:
    """Return hourly slots from 09:00 to 17:00 (inclusive)."""
    return [datetime.combine(target_date, time(hour=hour, minute=0)) for hour in range(9, 18)]


async def init_db() -> None:
    """Create tables and insert an idempotent seed doctor."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Doctor).where(Doctor.name == "Dr. Ahuja"))
            doctor = result.scalar_one_or_none()
            if doctor is None:
                session.add(Doctor(name="Dr. Ahuja", specialty="General Medicine"))
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
            doctor_result = await session.execute(select(Doctor).where(Doctor.name == doctor_name))
            doctor = doctor_result.scalar_one_or_none()
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


async def book_appointment_db(doctor_name: str, patient_name: str, date_time: datetime) -> str:
    """Book an appointment if the exact slot is still available."""
    async with AsyncSessionLocal() as session:
        try:
            doctor_result = await session.execute(select(Doctor).where(Doctor.name == doctor_name))
            doctor = doctor_result.scalar_one_or_none()
            if doctor is None:
                return f"Doctor '{doctor_name}' not found."

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