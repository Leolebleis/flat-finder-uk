FROM python:3.12-slim
WORKDIR /app
COPY ui/requirements.txt ui/requirements.txt
RUN pip install --no-cache-dir -r ui/requirements.txt
COPY shared/ shared/
COPY ui/ ui/
EXPOSE 8000
CMD ["uvicorn", "ui.main:app", "--host", "0.0.0.0", "--port", "8000"]
