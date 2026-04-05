# 1. Base image
FROM python:3.11-slim

# 2. Environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# 3. Set work directory
WORKDIR /app

# 4. Install dependencies
# We copy only the requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy project
COPY . .

# 6. Default command (overridden by docker-compose)
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
