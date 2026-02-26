# Pi Deployment

## Prerequisites

- Docker + docker compose on the Pi
- Mediastack running at `/opt/mediastack/`
- Nginx in the mediastack docker-compose

## 1. Add flat-finder service to docker-compose.yml

Add to `/opt/mediastack/docker-compose.yml`:

```yaml
  flat-finder:
    build:
      context: /home/leo/Documents/code/disqt.com/flat-finder
      dockerfile: ui/Dockerfile
    container_name: flat-finder
    restart: unless-stopped
    volumes:
      - flat-finder-data:/app/data
    environment:
      - FLAT_FINDER_UI_DB=/app/data/flat_finder.db
      - FLAT_FINDER_API_URL=https://disqt.com/flat/api
      - FLAT_FINDER_API_KEY=${FLAT_FINDER_API_KEY}
    networks:
      - mediastack
```

Add to the `volumes:` section:

```yaml
  flat-finder-data:
```

Add `FLAT_FINDER_API_KEY` to `/opt/mediastack/.env`.

## 2. Add nginx location

Add to both HTTP and HTTPS server blocks in `/opt/mediastack/config/nginx/default.conf`:

```nginx
# Flat Finder
location /flat/ {
    set $upstream_flat http://flat-finder:8000;
    proxy_pass $upstream_flat;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 3. Build and start

```bash
cd /opt/mediastack
docker compose up -d --build flat-finder
docker compose restart nginx
```

## 4. Verify

```bash
curl http://raspberrypi/flat/
docker logs flat-finder
```

## 5. Rebuild after code changes

```bash
cd /opt/mediastack
docker compose up -d --build flat-finder
```
