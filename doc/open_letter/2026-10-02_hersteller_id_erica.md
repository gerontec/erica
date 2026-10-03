# Offener Brief: Hersteller-ID für das Open-Source-Programm „erica“

Ich veröffentliche diese Anfrage an das Bayerische Staatsministerium der Finanzen
und für Heimat. Jeder soll nachlesen können, wie der ERiC-Lizenzvertrag für ein
freies Programm mit öffentlichem Quellcode auszulegen ist. Die Antwort wird hier
ergänzt, sobald sie vorliegt.

- Original als PDF: [2026-10-02_hersteller_id_erica.pdf](2026-10-02_hersteller_id_erica.pdf)
- Stand: **Antwort ausstehend**

---

Georg Heiß · Lenggries · gh@heissa.de

Bayerisches Staatsministerium der Finanzen und für Heimat
Büro des Staatsministers
Odeonsplatz 4
80539 München

Nachrichtlich: Bayerisches Landesamt für Steuern, Dienststelle München, 80284 München
(Koordinierung ELSTER)

Lenggries, 2. Oktober 2026

**Bitte um Bestätigung: Hersteller-ID für das Open-Source-Programm „erica“**
Bezug: Hersteller-ID-Antrag vom 02.10.2026, ÜbermittlungsId c41d0ddc-ec07-45ab-abf9-0603d4416398

Sehr geehrte Damen und Herren,

ich entwickle das freie Programm „erica“, das die Einkommensteuer berechnet und die
Erklärung über ERiC prüft und übermittelt. Den Quellcode finden Sie unter
<https://github.com/gerontec/erica> (Branch `elster-api`). ERiC liefere ich unverändert und
nur im nötigen Umfang als Teil des Programms mit, in einem eigenen Ordner mit
Lizenzvertrag und Hinweis auf die Lizenz. Mein eigener Code steht unter der MIT-Lizenz.

**Meine Auffassung:** Kommerzielle Anbieter liefern ihre Hersteller-ID im Programm mit
aus. Die ID kennzeichnet das Produkt, nicht den einzelnen Nutzer. Das gilt nach meinem
Verständnis auch für das unveränderte „erica“: Es ist ein einheitliches Produkt im Sinne
von § 4 Abs. 1 des ERiC-Lizenzvertrags, und seine Nutzer dürfen die ID als Teil davon
verwenden. Daran ändert sich nichts, wenn der Quellcode öffentlich ist und die ID dort
steht.

**Meine Bitte:** Bitte bestätigen Sie mir, dass diese Auffassung richtig ist. Falls etwas
dagegen spricht, teilen Sie mir bitte mit, was.

**Mitgelieferte ERiC-Bibliotheken:** Nach Ihrer Bestätigung lege ich ausschließlich
folgende Laufzeitbibliotheken (ERiC 44.3.6.0, Linux x86_64, unverändert) in das
Repository, zusammen mit dem Lizenzvertrag im Wortlaut und einem Hinweis auf die Lizenz:

- libericapi, libericxerces, libeSigner, libotto
- Plugins: libcommonData, libcheckESt_2025, libcheckElsterNachricht

Nicht enthalten sind die übrigen Bibliotheken, die ERiC-Dokumentation, Header-Dateien,
Beispielprogramme und Testzertifikate. Bitte bestätigen Sie auch, dass diese Auswahl
zulässig ist.

Ich werde die ID und die Bibliotheken erst dann in das öffentliche Repository übernehmen,
wenn Sie mir bestätigt haben, dass ich das darf. Veränderte Ableger von „erica“ müssten
eine eigene ID beantragen. Die Datenschutzhinweise nach § 5 und § 15 des Lizenzvertrags
zeigt das Programm vor der ersten Nutzung an, und ich halte ERiC auf der jeweiligen
Mindestversion.

Über eine Antwort bis zum 30. November 2026 würde ich mich freuen, damit das Programm
für die Erklärungen zum Veranlagungszeitraum 2025 bereitsteht.

Mit freundlichen Grüßen

Georg Heiß
