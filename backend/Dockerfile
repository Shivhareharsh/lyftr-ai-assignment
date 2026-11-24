# ---------- Build stage ----------
    FROM python:3.12-slim AS builder

    WORKDIR /build
    
    COPY requirements.txt .
    
    RUN pip install \
        --no-cache-dir \
        --prefix=/install \
        -r requirements.txt
    
    
    # ---------- Runtime stage ----------
    FROM python:3.12-slim AS runtime
    
    WORKDIR /app
    
    COPY --from=builder /install /usr/local
    
    COPY app ./app
    
    RUN mkdir -p /data
    
    EXPOSE 8000
    
    CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]