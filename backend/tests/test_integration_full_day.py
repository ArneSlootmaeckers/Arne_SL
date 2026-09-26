"""Integration test: a full day at the attraction with several visitors,
a manual override, gate checks and the daily report — exercised entirely
through the HTTP API, the way the real screens would use it.
"""
from __future__ import annotations

from app.domain.calendar import local_today
from app.services.common import now_utc


def test_full_day_simulation(client, supervisor_employee, test_settings):
    host = {"device_id": "host-1"}
    gate = {"device_id": "gate-1"}

    def scan_host(wristband_id):
        return client.post("/api/host/scan", json={"wristband_id": wristband_id, **host}).json()

    def verdict(v):
        return client.post("/api/host/verdict", json={"verdict": v, **host}).json()

    def scan_gate(wristband_id):
        return client.post("/api/gate/scan", json={"wristband_id": wristband_id, **gate}).json()

    # Bezoeker A: slaagt meteen.
    assert scan_host("A")["status"] == "NOG_NIET_GESPRONGEN"
    assert verdict("GROEN")["status"] == "GESLAAGD"
    assert scan_gate("A")["allowed"] is True

    # Bezoeker B: eerst fout, dan goed op de herkansing.
    assert scan_host("B")["status"] == "NOG_NIET_GESPRONGEN"
    assert verdict("ROOD")["status"] == "HERKANSING"
    assert scan_gate("B")["allowed"] is False
    assert scan_host("B")["status"] == "HERKANSING"
    assert verdict("GROEN")["status"] == "GESLAAGD"
    assert scan_gate("B")["allowed"] is True

    # Bezoeker C: twee keer fout, mag de rest van de dag niet meer springen.
    assert scan_host("C")["status"] == "NOG_NIET_GESPRONGEN"
    assert verdict("ROOD")["status"] == "HERKANSING"
    assert scan_host("C")["status"] == "HERKANSING"
    assert verdict("ROOD")["status"] == "NIET_GESLAAGD"
    derde_poging = scan_host("C")
    assert derde_poging["status"] == "NIET_GESLAAGD"
    assert derde_poging["requires_verdict"] is False
    assert scan_gate("C")["allowed"] is False

    # Bezoeker A komt terug voor een oefensprong.
    oefensprong = scan_host("A")
    assert oefensprong["status"] == "GESLAAGD"
    assert oefensprong["requires_practice_ack"] is True
    ack = client.post("/api/host/practice-ack", json=host)
    assert ack.status_code == 200

    # Supervisor corrigeert bandje C handmatig na overleg (bv. video herbekeken).
    login = client.post("/api/auth/login", json={"pincode": "5678"}).json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    override = client.post(
        "/api/admin/wristbands/C/status",
        json={"status": "GESLAAGD", "reason": "Sprong alsnog goedgekeurd na herbekijken video"},
        headers=headers,
    )
    assert override.status_code == 200
    assert scan_gate("C")["allowed"] is True

    # Dagoverzicht klopt met de geoordeelde sprongen van vandaag:
    # A groen->GESLAAGD, B rood->HERKANSING, B groen->GESLAAGD,
    # C rood->HERKANSING, C rood->NIET_GESLAAGD (de handmatige wijziging telt niet
    # mee als testsprong-oordeel), en 1 oefensprong (A).
    today = local_today(now_utc(), test_settings.tz)
    report = client.get(f"/api/admin/report?report_date={today.isoformat()}", headers=headers)
    assert report.status_code == 200
    body = report.json()
    assert body["geslaagd"] == 2
    assert body["herkansing"] == 2
    assert body["niet_geslaagd"] == 1
    assert body["totaal_testsprongen"] == 5
    assert body["oefensprongen"] == 1
    assert body["gemiddelde_tijd_tussen_sprongen_seconden"] is not None
