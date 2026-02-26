# Flat Finder -- VPS Deployment

## 1. Clone and set up

```bash
cd /home/dev/projects
git clone <repo-url> flat-finder
cd flat-finder
python3 -m venv venv
source venv/bin/activate
pip install -r scraper/requirements.txt -r api/requirements.txt
```

## 2. Configure environment

```bash
cp .env.example .env
# Edit .env -- set FLAT_FINDER_API_KEY, NTFY_TOPIC, GMAIL creds, search params
nano .env
```

## 3. Install systemd units

```bash
sudo cp deploy/flat-finder-api.service /etc/systemd/system/
sudo cp deploy/flat-finder-scraper.service /etc/systemd/system/
sudo cp deploy/flat-finder-scraper.timer /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now flat-finder-api.service
sudo systemctl enable --now flat-finder-scraper.timer
```

## 4. Nginx config

Add to the server block in `/etc/nginx/sites-enabled/disqt.com`:

```nginx
location /flat/api/ {
    proxy_pass http://127.0.0.1:8090/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Verify

```bash
# Check services
systemctl status flat-finder-api.service
systemctl status flat-finder-scraper.timer
systemctl list-timers flat-finder-scraper.timer

# Run scraper manually
sudo systemctl start flat-finder-scraper.service
journalctl -u flat-finder-scraper.service -n 20

# Test API
curl -H "X-Api-Key: <your-key>" https://disqt.com/flat/api/stats
```

## 6. Update

```bash
cd /home/dev/projects/flat-finder
git pull
source venv/bin/activate
pip install -r scraper/requirements.txt -r api/requirements.txt
sudo systemctl restart flat-finder-api.service
```
