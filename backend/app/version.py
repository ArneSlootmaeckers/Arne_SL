"""Versie van deze installatie, en wat ze van de Android-app verwacht.

Bij een nieuwe release (zie docs/handleiding-beheer.md, "Updates"):
- APP_VERSION verhogen, gelijk aan de tag op GitHub zonder "v"
  (bv. tag v1.3.0 -> "1.3.0", beta v1.4.0-beta.1 -> "1.4.0-beta.1"). De
  updater weigert een release waarvan dit getal niet met de tag overeenkomt.
- MIN_ANDROID_VERSION_CODE verhogen als deze serverversie een nieuwere app
  nodig heeft (versionCode uit android/webview-app/app/build.gradle.kts).
  Een oudere app toont dan een updatevenster, zodra die nieuwe versie ook
  echt in de Play Store staat.
"""

APP_VERSION = "1.0.1"
MIN_ANDROID_VERSION_CODE = 2
