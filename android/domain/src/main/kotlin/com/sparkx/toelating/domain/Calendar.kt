package com.sparkx.toelating.domain

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/**
 * Pure date/timezone helpers for the Europe/Brussels day boundary.
 *
 * Direct port of backend/app/domain/calendar.py. Uses java.time's IANA
 * timezone database (bundled in the JVM/Android, no network I/O), so the
 * day-rollover rule stays correct across DST transitions.
 *
 * Note: unlike Python's `datetime`, an `Instant` can never be "naive" (it
 * has no concept of a missing timezone) — the ValueError guard the Python
 * version needs for that case is structurally impossible here, so it's
 * simply not ported.
 */
val BRUSSELS_TZ: ZoneId = ZoneId.of("Europe/Brussels")

/** Convert a UTC instant to the local (Brussels) calendar date. */
fun localToday(nowUtc: Instant, tz: ZoneId = BRUSSELS_TZ): LocalDate =
    nowUtc.atZone(tz).toLocalDate()

/** The UTC [start, end) instant range corresponding to one local calendar day. */
fun localDayUtcRange(day: LocalDate, tz: ZoneId = BRUSSELS_TZ): Pair<Instant, Instant> {
    val startLocal = day.atStartOfDay(tz)
    val endLocal = startLocal.plusDays(1)
    return startLocal.toInstant() to endLocal.toInstant()
}
