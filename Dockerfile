# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code
COPY . .

# Run the database initialization script
#RUN python init_db.py

# Expose the port Gunicorn will run on
EXPOSE 5000

# Run the app using Gunicorn
# This is the key change for production!
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]
