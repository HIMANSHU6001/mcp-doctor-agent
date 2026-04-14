from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP

from database import (
    book_appointment_db as book_appointment_db_helper,
    get_doctor_availability as get_doctor_availability_helper,
)

mcp = FastMCP("DoctorAssistant")


@mcp.tool()
async def get_doctor_availability_tool(doctor_name: str, date: str) -> str:
    """Get available appointment times for a doctor on a specific date.

    This MCP tool is designed for LLM-driven scheduling workflows where the model needs
    to answer "When is this doctor free?" with concrete, formatted time options.
    The tool delegates all persistence and scheduling logic to the asynchronous database
    helper in `database.py`, so callers do not need direct SQL access.

    Use this tool before booking an appointment. The expected flow is:
    1. Ask for availability on a date.
    2. Inspect returned slots.
    3. Pick one slot and call the booking tool.

    The `date` argument must be an ISO calendar date string in `YYYY-MM-DD` format.
    Example valid value: `2026-04-14`.
    Invalid formats (for example `14-04-2026`, `04/14/2026`, or natural language
    text) will return a descriptive error message from the database helper.

    The response is always a plain string intended for conversational use. Depending
    on database state and validation, the string can represent:
    - A successful availability list including free hourly slots.
    - A doctor-not-found message.
    - A no-slots-available message for the requested date.
    - A date-format validation message.
    - A database error message when a query fails.

    Args:
        doctor_name (str): Full display name of the doctor to query, such as
            "Dr. Ahuja". Matching depends on how names are stored in the database.
            Use the exact canonical name to avoid not-found responses.
        date (str): Target date for availability lookup in strict `YYYY-MM-DD`
            format. The date is interpreted as a single local calendar day.

    Returns:
        str: Human-readable availability output or a descriptive failure/status
        message. The string is safe to show directly to end users or to parse in
        an orchestration layer.

    Raises:
        None: This wrapper does not intentionally raise domain exceptions; it
        forwards the helper result string so MCP clients receive deterministic
        tool output.

    Examples:
        Basic lookup:
            >>> await get_doctor_availability_tool("Dr. Ahuja", "2026-04-14")
            "Available slots for Dr. Ahuja on 2026-04-14: 09:00, 10:00, ..."

        Invalid date input:
            >>> await get_doctor_availability_tool("Dr. Ahuja", "14-04-2026")
            "Invalid date format. Please use YYYY-MM-DD."

    Notes:
        - The tool is asynchronous and must be awaited.
        - Scheduling policy (time windows and slot intervals) is controlled by
          the database helper implementation, not by this wrapper.
        - This tool does not mutate data; it performs read-only availability checks.
    """
    return await get_doctor_availability_helper(doctor_name=doctor_name, date=date)


@mcp.tool()
async def book_appointment_tool(doctor_name: str, patient_name: str, date_time: datetime) -> str:
    """Book a doctor appointment for a patient at an exact date-time slot.

    This MCP tool creates a new appointment by delegating to the asynchronous
    booking helper in `database.py`. It is intended for use after availability has
    been confirmed, and enforces collision checks to prevent duplicate booking of
    the same doctor at the same timestamp.

    Input semantics are strict:
    - `doctor_name` should match a doctor record that already exists.
    - `patient_name` should be the patient-facing full name to store.
    - `date_time` should represent the exact target slot as a Python `datetime`.

    In common MCP workflows, clients serialize date-time values in ISO-8601 form
    and the framework resolves them into a `datetime` object before invocation.
    A typical value is equivalent to `2026-04-14T10:00:00`.

    The response is always a plain string with a deterministic status message,
    suitable for direct conversational output and orchestration branching. The
    returned text may indicate:
    - Successful booking with patient name, doctor name, and scheduled time.
    - Doctor not found.
    - Slot conflict when the exact doctor/date-time is already scheduled.
    - Database failure details if write operations fail.

    Args:
        doctor_name (str): Canonical doctor name to book against (for example,
            "Dr. Ahuja"). If the doctor does not exist, booking is rejected.
        patient_name (str): Name of the patient for whom the appointment is being
            created. This is stored in the `appointments` table.
        date_time (datetime): Exact appointment timestamp for the requested slot.
            Provide a precise value that matches the intended schedule time.

    Returns:
        str: A success, conflict, not-found, or error message generated by the
        booking helper. The caller can present this string to users as-is.

    Raises:
        None: This wrapper is designed to return helper status text rather than
        raise domain errors to callers.

    Examples:
        Successful booking path:
            >>> await book_appointment_tool(
            ...     doctor_name="Dr. Ahuja",
            ...     patient_name="Riya Sharma",
            ...     date_time=datetime(2026, 4, 14, 10, 0),
            ... )
            "Appointment booked for Riya Sharma with Dr. Ahuja on 2026-04-14 10:00."

        Conflict path:
            >>> await book_appointment_tool(
            ...     doctor_name="Dr. Ahuja",
            ...     patient_name="Aman Verma",
            ...     date_time=datetime(2026, 4, 14, 10, 0),
            ... )
            "Slot already booked for Dr. Ahuja at 2026-04-14 10:00."

    Notes:
        - This tool mutates persistent state by inserting a new appointment row.
        - Collision behavior is delegated to the DB helper and currently checks
          exact date-time equality for scheduled appointments.
        - Use availability lookup first to reduce user-facing conflict responses.
    """
    return await book_appointment_db_helper(
        doctor_name=doctor_name,
        patient_name=patient_name,
        date_time=date_time,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")