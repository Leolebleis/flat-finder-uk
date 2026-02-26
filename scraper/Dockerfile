FROM python:3.12-slim
WORKDIR /app
COPY scraper/requirements.txt scraper/requirements.txt
RUN pip install --no-cache-dir -r scraper/requirements.txt
COPY shared/ shared/
COPY scraper/ scraper/
VOLUME /app/data
ENV FLAT_FINDER_DB=/app/data/scraper.db
CMD ["sh", "-c", "while true; do python -m scraper.scraper; sleep 900; done"]
