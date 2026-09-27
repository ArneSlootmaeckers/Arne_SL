package com.sparkx.toelating.domain

import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

/** Mirrors TestEffectiveStatus in backend/tests/test_day_rollover.py. */
class EffectiveStatusTest {
    @Test
    fun `no stored status is not yet jumped`() {
        assertEquals(
            Status.NOG_NIET_GESPRONGEN,
            effectiveStatus(null, null, LocalDate.of(2026, 6, 1)),
        )
    }

    @Test
    fun `stored status from today is kept`() {
        val today = LocalDate.of(2026, 6, 1)
        for (status in Status.entries) {
            assertEquals(status, effectiveStatus(status, today, today), "status=$status")
        }
    }

    @Test
    fun `stored status from yesterday resets to not yet jumped`() {
        val yesterday = LocalDate.of(2026, 6, 1)
        val today = LocalDate.of(2026, 6, 2)
        for (stored in listOf(Status.HERKANSING, Status.GESLAAGD, Status.NIET_GESLAAGD)) {
            assertEquals(
                Status.NOG_NIET_GESPRONGEN,
                effectiveStatus(stored, yesterday, today),
                "stored=$stored",
            )
        }
    }

    @Test
    fun `stored status from a previous day long ago also resets`() {
        assertEquals(
            Status.NOG_NIET_GESPRONGEN,
            effectiveStatus(Status.GESLAAGD, LocalDate.of(2025, 1, 1), LocalDate.of(2026, 6, 2)),
        )
    }
}

/**
 * A fixed UTC offset would misplace visitors near local midnight in summer (CEST,
 * UTC+2) vs winter (CET, UTC+1). These pin down both cases against the real
 * Europe/Brussels rules using java.time's tz database, and the actual 2026 DST
 * transition dates (spring forward 2026-03-29, fall back 2026-10-25).
 *
 * Mirrors TestBrusselsDayBoundaryAcrossDST in backend/tests/test_day_rollover.py
 * (minus the "requires timezone-aware input" case, which doesn't apply to Instant
 * — see the note in Calendar.kt).
 */
class BrusselsDayBoundaryAcrossDstTest {
    private fun utc(y: Int, mo: Int, d: Int, h: Int, mi: Int): Instant =
        LocalDate.of(y, mo, d).atTime(h, mi).toInstant(ZoneOffset.UTC)

    @Test
    fun `winter local midnight boundary CET UTC plus 1`() {
        assertEquals(LocalDate.of(2026, 1, 14), localToday(utc(2026, 1, 14, 22, 30)))
        assertEquals(LocalDate.of(2026, 1, 15), localToday(utc(2026, 1, 14, 23, 30)))
    }

    @Test
    fun `summer local midnight boundary CEST UTC plus 2`() {
        assertEquals(LocalDate.of(2026, 7, 14), localToday(utc(2026, 7, 14, 21, 30)))
        // An hour earlier in UTC than the winter case, because CEST is UTC+2.
        assertEquals(LocalDate.of(2026, 7, 15), localToday(utc(2026, 7, 14, 22, 30)))
    }

    @Test
    fun `naive fixed offset would misdate the summer case`() {
        // The same UTC instant that is already "tomorrow" in Brussels (CEST) is still
        // "today" under plain UTC-date truncation, proving a hardcoded offset breaks here.
        val instant = utc(2026, 7, 14, 22, 30)
        assertEquals(LocalDate.of(2026, 7, 14), instant.atZone(ZoneOffset.UTC).toLocalDate())
        assertNotEquals(instant.atZone(ZoneOffset.UTC).toLocalDate(), localToday(instant))
        assertEquals(LocalDate.of(2026, 7, 15), localToday(instant))
    }

    @Test
    fun `spring forward transition 2026-03-29`() {
        // Clocks jump from 02:00 CET to 03:00 CEST at 01:00 UTC, well after local
        // midnight, so the calendar date must stay March 29 on both sides.
        assertEquals(LocalDate.of(2026, 3, 29), localToday(utc(2026, 3, 29, 0, 59)))
        assertEquals(LocalDate.of(2026, 3, 29), localToday(utc(2026, 3, 29, 1, 1)))
    }

    @Test
    fun `fall back transition 2026-10-25`() {
        // Clocks fall from 03:00 CEST to 02:00 CET at 01:00 UTC (local 02:00-03:00
        // occurs twice). The calendar date must stay October 25 throughout.
        assertEquals(LocalDate.of(2026, 10, 25), localToday(utc(2026, 10, 25, 0, 59)))
        assertEquals(LocalDate.of(2026, 10, 25), localToday(utc(2026, 10, 25, 1, 1)))
    }
}
