package com.sparkx.toelating.domain

/**
 * Pure status domain logic for the wristband admission system.
 *
 * No I/O, no database, no Android dependencies. Direct port of
 * backend/app/domain/status.py — keep the two in sync if the rules change.
 */
enum class Status {
    NOG_NIET_GESPRONGEN,
    HERKANSING,
    GESLAAGD,
    NIET_GESLAAGD,
}

enum class Verdict {
    GROEN,
    ROOD,
}

/** Raised when a verdict is submitted for a status that no longer accepts one. */
class VerdictNotAllowedError(message: String) : Exception(message)

data class VerdictResult(
    val newStatus: Status,
    val statusChanged: Boolean,
    val isPracticeJump: Boolean,
)

// Statuses for which the test jump still allows an attempt (all except NIET_GESLAAGD).
private val TEST_JUMP_ALLOWED = setOf(Status.NOG_NIET_GESPRONGEN, Status.HERKANSING, Status.GESLAAGD)

// The transition table from section 2 of the assignment: (current status, verdict) -> next status.
private val TRANSITIONS: Map<Pair<Status, Verdict>, Status> = mapOf(
    (Status.NOG_NIET_GESPRONGEN to Verdict.GROEN) to Status.GESLAAGD,
    (Status.NOG_NIET_GESPRONGEN to Verdict.ROOD) to Status.HERKANSING,
    (Status.HERKANSING to Verdict.GROEN) to Status.GESLAAGD,
    (Status.HERKANSING to Verdict.ROOD) to Status.NIET_GESLAAGD,
    (Status.GESLAAGD to Verdict.GROEN) to Status.GESLAAGD,
    (Status.GESLAAGD to Verdict.ROOD) to Status.GESLAAGD,
)

/** Apply the day-rollover rule: a stored status only counts for the day it was recorded on. */
fun effectiveStatus(
    storedStatus: Status?,
    storedDate: java.time.LocalDate?,
    today: java.time.LocalDate,
): Status {
    if (storedStatus == null || storedDate == null || storedDate != today) {
        return Status.NOG_NIET_GESPRONGEN
    }
    return storedStatus
}

/**
 * Compute the result of a host verdict against a wristband's current effective status.
 *
 * Throws [VerdictNotAllowedError] for NIET_GESLAAGD, which never accepts a verdict again
 * for the rest of the day.
 */
fun applyVerdict(currentStatus: Status, verdict: Verdict): VerdictResult {
    if (currentStatus == Status.NIET_GESLAAGD) {
        throw VerdictNotAllowedError(
            "Status is ${Status.NIET_GESLAAGD}: geen oordeel meer toegestaan vandaag."
        )
    }
    val newStatus = TRANSITIONS.getValue(currentStatus to verdict)
    return VerdictResult(
        newStatus = newStatus,
        statusChanged = newStatus != currentStatus,
        isPracticeJump = currentStatus == Status.GESLAAGD,
    )
}

/** Whether a wristband with this status may still attempt the test jump. */
fun canAttemptTestJump(status: Status): Boolean = status in TEST_JUMP_ALLOWED

/** Whether a wristband with this status may pass the Ski Jump gate. */
fun canAccessSkiJump(status: Status): Boolean = status == Status.GESLAAGD

/** Whether a string is one of the four valid statuses (for manual admin overrides). */
fun isValidManualStatus(value: String): Boolean =
    try {
        Status.valueOf(value)
        true
    } catch (e: IllegalArgumentException) {
        false
    }
