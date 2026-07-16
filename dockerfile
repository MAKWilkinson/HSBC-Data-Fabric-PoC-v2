
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency file first (better layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project
COPY . .

# Command to run when the container starts
CMD ["python", "main.py"]