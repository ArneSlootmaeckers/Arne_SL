package com.sparkx.toelating.domain

import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Every transition from section 2 of the assignment, verified exactly. Mirrors
 * TestTransitionTable in backend/tests/test_status_domain.py. */
class TransitionTableTest {
    @Test
    fun `not yet jumped green becomes geslaagd`() {
        val result = applyVerdict(Status.NOG_NIET_GESPRONGEN, Verdict.GROEN)
        assertEquals(Status.GESLAAGD, result.newStatus)
        assertTrue(result.statusChanged)
        assertFalse(result.isPracticeJump)
    }

    @Test
    fun `not yet jumped red becomes herkansing`() {
        val result = applyVerdict(Status.NOG_NIET_GESPRONGEN, Verdict.ROOD)
        assertEquals(Status.HERKANSING, result.newStatus)
        assertTrue(result.statusChanged)
        assertFalse(result.isPracticeJump)
    }

    @Test
    fun `herkansing green becomes geslaagd`() {
        val result = applyVerdict(Status.HERKANSING, Verdict.GROEN)
        assertEquals(Status.GESLAAGD, result.newStatus)
        assertTrue(result.statusChanged)
        assertFalse(result.isPracticeJump)
    }

    @Test
    fun `herkansing red becomes niet geslaagd`() {
        val result = applyVerdict(Status.HERKANSING, Verdict.ROOD)
        assertEquals(Status.NIET_GESLAAGD, result.newStatus)
        assertTrue(result.statusChanged)
        assertFalse(result.isPracticeJump)
    }

    @Test
    fun `geslaagd stays geslaagd as practice jump for either verdict`() {
        for (verdict in Verdict.entries) {
            val result = applyVerdict(Status.GESLAAGD, verdict)
            assertEquals(Status.GESLAAGD, result.newStatus, "verdict=$verdict")
            assertFalse(result.statusChanged, "verdict=$verdict")
            assertTrue(result.isPracticeJump, "verdict=$verdict")
        }
    }

    @Test
    fun `niet geslaagd never accepts a verdict`() {
        for (verdict in Verdict.entries) {
            assertFailsWith<VerdictNotAllowedError>("verdict=$verdict") {
                applyVerdict(Status.NIET_GESLAAGD, verdict)
            }
        }
    }
}

/** Mirrors TestLocationAccess in backend/tests/test_status_domain.py. */
class LocationAccessTest {
    @Test
    fun `test jump access`() {
        assertTrue(canAttemptTestJump(Status.NOG_NIET_GESPRONGEN))
        assertTrue(canAttemptTestJump(Status.HERKANSING))
        assertTrue(canAttemptTestJump(Status.GESLAAGD))
        assertFalse(canAttemptTestJump(Status.NIET_GESLAAGD))
    }

    @Test
    fun `ski jump access requires geslaagd`() {
        assertFalse(canAccessSkiJump(Status.NOG_NIET_GESPRONGEN))
        assertFalse(canAccessSkiJump(Status.HERKANSING))
        assertTrue(canAccessSkiJump(Status.GESLAAGD))
        assertFalse(canAccessSkiJump(Status.NIET_GESLAAGD))
    }
}

/** Mirrors TestManualStatusValidation in backend/tests/test_status_domain.py. */
class ManualStatusValidationTest {
    @Test
    fun `all four statuses are valid`() {
        for (status in Status.entries) {
            assertTrue(isValidManualStatus(status.name), "status=$status")
        }
    }

    @Test
    fun `invalid values are rejected`() {
        for (value in listOf("", "GESLAAGD ", "geslaagd", "ONBEKEND", "NONE")) {
            assertFalse(isValidManualStatus(value), "value='$value'")
        }
    }
}
