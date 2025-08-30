# 📖 Documentation complète Scalp Bot


---

# Scalp Bot

Bot de scalping crypto pour serveur (Linux + systemd).  
Il exécute des stratégies de trading, gère plusieurs symboles et publie un **dashboard** en continu.

---

📚 Documentation :  
- [Installation](docs/install.md)  
- [Configuration](docs/config.md)  
- [Dashboard](docs/dashboard.md)  
- [Services systemd](docs/services.md)  
- [Maintenance](docs/maintenance.md)  


---

# 🚀 Installation

```bash
git clone https://github.com/<ton-repo>.git /opt/scalp
cd /opt/scalp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


---

# 🔧 Configuration

Le bot utilise un fichier `.env` à la racine :

```ini
EXCHANGE=bitget
API_KEY=xxx
API_SECRET=xxx
API_PASSPHRASE=xxx
SYMBOLS=BTCUSDT,ETHUSDT
TIMEFRAMES=1m,5m,15m


---

# 📊 Dashboard

Le dashboard est généré automatiquement toutes les 5 minutes par `publish_dashboard.sh`.

- Généré : `/opt/scalp/dashboard.html`  
- Copié vers : `/opt/scalp/docs/index.html`  

Il est ensuite publié sur la branche `gh-pages`.


---

# 🛠️ Services systemd

## Bot principal
```bash
systemctl status scalp-bot.service
journalctl -u scalp-bot.service -f


## Dashboard
systemctl status scalp-dashboard.service
journalctl -u scalp-dashboard.service -f


---

# 🧹 Maintenance

## Nettoyage Git
- `publish_dashboard.sh` reconstruit et pousse automatiquement le dashboard
- `.gitignore` exclut `dashboard.html`

## Nettoyage fichiers inutiles
```bash
rm -f *.bak *.old *.swp dashboard.html

## Logs en direct
journalctl -u scalp-bot.service -f

