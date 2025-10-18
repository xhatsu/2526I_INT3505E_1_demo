# Use a slim Python base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Run the app using Gunicorn for production
# '-w 4' means 4 worker processes. Adjust as needed.
# '-b 0.0.0.0:5000' binds to all network interfaces.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]