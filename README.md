# Kalorien-Tagebuch – Self-Hosted

Kleine Web-App zum Kalorienzählen mit Fokus aufs **Zunehmen**: Du schreibst in
normaler Sprache hin, was du gegessen hast, Claude schätzt Kalorien und Eiweiß,
und die App zeigt dir, wie nah du an deinem Tagesziel bist.

Läuft komplett auf dem eigenen Server. Außer der Anthropic-API für die
Schätzungen wird kein externer Dienst gebraucht.

## Funktionen

- **Freitext-Eingabe** – „2 Scheiben Toast mit Butter" reicht, kcal und Eiweiß
  werden geschätzt und lassen sich nachträglich korrigieren
- **Konten mit E-Mail-Code** – mehrere Personen parallel, jede sieht nur ihre
  eigenen Daten, kein Passwort nötig
- **Tagesziel** mit Fortschrittsbalken und „noch X kcal bis …"
- **KI-Einschätzung** – bewertet die letzten 14 Tage gegenüber dem Ziel und sagt,
  wo du nachgelassen hast (auf Zunehmen ausgelegt)
- **Verlauf** – 7, 14 oder 30 Tage, beliebig weiter zurückblätterbar; ein Klick
  auf einen Balken zeigt, was an dem Tag wann gegessen wurde
- **Schnellwahl** – feste Chips für die üblichen Gerichte und Getränke, ein Tap
  genügt (ohne neuen API-Aufruf)
- **Gewichts-Tracking** mit Trend über 30 Tage
- **CSV-Export** aller Einträge

## 1. Voraussetzungen

- Docker + Docker Compose auf dem Zielrechner (z. B. eine LXC/VM im Proxmox-Home-Lab)
- Ein Anthropic API-Key: https://console.anthropic.com/settings/keys
- Eine Domain oder Subdomain, die auf den Server zeigt (siehe Schritt 4)

Für einen unprivilegierten LXC-Container in Proxmox muss unter
*Options → Features* **Nesting** aktiviert sein, sonst startet Docker nicht.

## 2. App starten

```bash
cp .env.example .env
# .env öffnen und mindestens ANTHROPIC_API_KEY eintragen

docker compose up -d --build
```

Die App läuft danach auf Port 5000 (`http://<server-ip>:5000`).
Die Datenbank liegt persistent unter `./data/kalorien.db` – Container-Neustarts
und Updates löschen deine Einträge nicht.

> Die Datei `.env` muss existieren, bevor `docker compose up` läuft – sonst
> bricht Compose mit einer Fehlermeldung ab.

## 3. Anmeldung und Konten

Beim Aufruf der Seite landest du auf `/login`. Dort gibst du deine
E-Mail-Adresse ein und bekommst einen 6-stelligen Code. Beim ersten
erfolgreichen Code wird automatisch ein Konto angelegt.

**Ohne konfigurierten Mailserver** steht der Code im Container-Log:

```bash
docker compose logs --tail=30 kalorien-tagebuch
```

### Code per E-Mail verschicken

Damit jede Person ihren Code selbst bekommt, brauchst du einen SMTP-Zugang.
Die App verschickt selbst keine Mails über die eigene IP – das würde in
Spam-Ordnern landen –, sondern über den Postausgangsserver deines
Mail-Anbieters. Trag die Daten in die `.env` ein und starte neu:

```bash
docker compose up -d
```

**Gmail** (braucht aktivierte Zwei-Faktor-Anmeldung, dann unter
myaccount.google.com/apppasswords ein App-Passwort erzeugen – nicht das
normale Google-Passwort verwenden):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=deine-adresse@gmail.com
SMTP_PASSWORD=das-16-stellige-app-passwort
SMTP_FROM=deine-adresse@gmail.com
```

**Anderer Anbieter:** Such in dessen Hilfe nach „SMTP" oder
„Postausgangsserver". Meist ist es `smtp.<anbieter>.de`, Port `587` mit
`SMTP_SECURITY=starttls` oder Port `465` mit `SMTP_SECURITY=ssl`. Den Port
kannst du weglassen, dann wird der zur Verschlüsselung passende genommen.

Bei den meisten Anbietern muss `SMTP_FROM` dieselbe Adresse sein wie
`SMTP_USER`, sonst wird der Versand abgelehnt.

Klappt der Versand nicht, steht der Grund im Log
(`docker compose logs kalorien-tagebuch`) – der Code selbst wird dabei nie
in einer Fehlermeldung nach außen gegeben.

### Wer darf sich registrieren?

Standardmäßig darf sich nur das **erste** Konto anlegen – deins. Danach ist die
Registrierung zu. Das ist Absicht: Die App ist meist öffentlich erreichbar, und
ein fremdes Konto würde deine Anthropic-Kosten verursachen.

Weitere Personen schaltest du in der `.env` frei (deine Adresse mit aufführen):

```
ALLOWED_EMAILS=du@example.com,partnerin@example.com
```

Wer die Registrierung wirklich für alle offen haben will, setzt
`REGISTRATION_OPEN=true` – sinnvoll nur mit einem Zugriffsschutz davor,
etwa Cloudflare Access.

Hattest du die App vorher schon ohne Konten benutzt, übernimmt das erste
registrierte Konto alle bestehenden Einträge. Melde dich also selbst als Erste
an, bevor du anderen den Link gibst.

## 4. Über die eigene Domain erreichbar machen

### Variante A: Cloudflare Tunnel (kein Port-Forwarding nötig)

Wenn schon ein `cloudflared`-Tunnel läuft – etwa als Home-Assistant-Add-on –
reicht ein zusätzlicher Eintrag in dessen Konfiguration:

```yaml
- hostname: kcal.deine-domain.tld
  service: http://192.168.2.114:5000
```

Wichtig: **kein Schrägstrich am Ende** der `service`-URL, sonst verweigert
cloudflared den Start mit `ingress rules don't support proxying to a different path`.

Danach das Add-on neu starten und bei Cloudflare unter **DNS → Add record** einen
Eintrag vom Typ **Tunnel** für `kcal` auf denselben Tunnel anlegen.

Privat halten geht am einfachsten über **Cloudflare Access** (Zero-Trust-Dashboard
→ Access → Applications → Self-hosted → Public DNS): dann fragt Cloudflare vor
der App nach einer freigegebenen E-Mail-Adresse.

### Variante B: Reverse Proxy mit Port-Forwarding

Alternativ ein Reverse Proxy wie Nginx Proxy Manager oder Caddy, Ports 80/443
im Router weitergeleitet, Let's-Encrypt-Zertifikat über den Proxy:

```
kcal.deine-domain.tld {
    reverse_proxy localhost:5000
}
```

Das Secure-Flag am Session-Cookie setzt die App automatisch passend zum
Aufrufweg – die Anmeldung funktioniert also sowohl über `https://…` als auch
über `http://<server-ip>:5000` im LAN, ohne dass du etwas konfigurieren musst.

## 5. Updates einspielen

```bash
git pull
docker compose up -d --build
```

Schema-Änderungen werden beim Start automatisch angewendet, bestehende Daten
bleiben erhalten.

## Kosten und Modellwahl

Die einzigen laufenden Kosten sind Anthropic-API-Aufrufe. Standardmäßig läuft die
App auf `claude-haiku-4-5` – dem günstigsten Modell, das für Kalorienschätzungen
in der Praxis gut ausreicht. Bei privater Nutzung liegt das im Bereich von
Cent-Beträgen pro Monat.

Wenn die Schätzungen genauer werden sollen, in der `.env`:

```
ANTHROPIC_MODEL=claude-sonnet-5
```

Ein Aufruf entsteht pro neuem Freitext-Eintrag und einmal täglich für die
Einschätzung; Einträge über die Schnellwahl-Chips kosten nichts.

## Konfiguration

Alle Variablen sind in [`.env.example`](.env.example) dokumentiert. Die
wichtigsten:

| Variable | Standard | Bedeutung |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Pflicht |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Modell für Schätzung und Einschätzung |
| `APP_TZ` | `Europe/Berlin` | Zeitzone für Datum und Uhrzeit der Einträge |
| `COOKIE_SECURE` | automatisch | Richtet sich nach HTTP/HTTPS; nur zum Überschreiben |
| `SECRET_KEY` | automatisch | Ändern macht alle Anmeldungen ungültig |
| `ALLOWED_EMAILS` | leer | Kommaliste freigegebener Adressen |
| `REGISTRATION_OPEN` | leer | `true` = jede Adresse darf sich registrieren |
| `SMTP_*` | leer | Ohne Angabe steht der Anmeldecode im Log |

## Hinweise

Kalorienangaben sind Schätzungen auf Basis üblicher Portionsgrößen, keine exakte
Nährwertanalyse. Die KI-Einschätzung ist keine medizinische Beratung.

## Backup

Es reicht, den Ordner `data/` zu sichern – dort liegen Datenbank und
Session-Schlüssel:

```bash
tar czf kalorien-backup-$(date +%F).tar.gz data/
```
