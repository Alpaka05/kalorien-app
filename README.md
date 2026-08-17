# Kalorien-Tagebuch – Self-Hosted

Kleine Web-App mit SQLite-Datenbank. Alle Geräte, die die Seite über deine Domain
öffnen, sehen dieselben Daten – kein Login nötig, kein externer Dienst außer der
Anthropic-API für die Kalorienschätzung.

## 1. Voraussetzungen

- Docker + Docker Compose auf dem Zielrechner (z. B. eine LXC/VM in deinem Proxmox-Home-Lab)
- Ein Anthropic API-Key: https://console.anthropic.com/settings/keys
- Deine Domain `alpaka.yt` (oder eine Subdomain wie `kalorien.alpaka.yt`), die per DNS
  auf die öffentliche IP deines Home Labs zeigt

## 2. App starten

```bash
cp .env.example .env
# .env öffnen und ANTHROPIC_API_KEY eintragen

docker compose up -d --build
```

Die App läuft danach lokal auf Port 5000 (`http://<server-ip>:5000`).
Die Datenbank liegt persistent unter `./data/kalorien.db` – Container-Neustarts
oder Updates löschen deine Einträge also nicht.

## 3. Über alpaka.yt erreichbar machen

Am einfachsten mit einem Reverse Proxy, der auch gleich automatisch HTTPS-Zertifikate
holt. Zwei gängige Optionen für ein Home Lab:

### Option A: Nginx Proxy Manager (Weboberfläche, gut wenn du schon einen für Home Assistant nutzt)
1. Neuer Proxy Host → Domain: `kalorien.alpaka.yt`
2. Forward Hostname/IP: IP des Containers/Hosts, Port `5000`
3. SSL-Tab: Let's Encrypt-Zertifikat anfordern, "Force SSL" aktivieren

### Option B: Caddy (eine Zeile Konfiguration)
```
kalorien.alpaka.yt {
    reverse_proxy localhost:5000
}
```
Caddy holt sich das Zertifikat automatisch.

### DNS
Bei deinem Domain-Provider einen A-Record (oder CNAME) für
`kalorien.alpaka.yt` auf deine öffentliche IP anlegen. Falls sich deine IP
ändert (kein statisches IP), lohnt sich zusätzlich ein Dyn-DNS-Client.

## 4. Nutzung

Einfach `https://kalorien.alpaka.yt` auf jedem Gerät öffnen – Handy, Laptop, etc.
Alle sehen dieselben Einträge, weil die Daten zentral auf deinem Server liegen.

## Kosten

Die einzigen laufenden Kosten sind die Anthropic-API-Aufrufe für die Kalorienschätzung
(Claude Sonnet). Bei privater Nutzung (ein paar Einträge täglich) liegt das im Bereich
von Cent-Beträgen pro Monat.
