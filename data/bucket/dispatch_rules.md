# Dispatch Rules — AIRMAN Flight School

## Section 1: Duty Hour Rules
- Instructor max duty: 8 hours/day including briefing/debrief (30 min each)
- Student max flight time: 4 hours/day
- Minimum rest between duty days: 10 hours

## Section 2: Sortie Pairing Constraints
- Each FLIGHT sortie requires exactly one instructor (except SOLO).
- SOLO sorties: no instructor required; student must be solo_eligible.
- SIM sortie requires sim_instructor=true instructor.
- Instructor rating must include the sortie type.

## Section 3: Aircraft Constraints
- Aircraft type must match student stage requirements.
- Aircraft in MAINTENANCE status cannot be assigned.
- GROUNDED aircraft cannot be assigned.
- Max 2 sorties per aircraft per day.

## Section 4: Booking Rules
- No double-booking: student, instructor, aircraft each appear in max 1 slot at a time.
- Slots must not overlap for any resource.
- Minimum ground time between sorties for same aircraft: 30 minutes.

## Section 5: Solo Eligibility
- solo_eligible flag must be true on the student record.
- Instructor endorsement must be current (within 90 days).
- Weather minima for solo are stricter (see weather_minima.md Section 2).