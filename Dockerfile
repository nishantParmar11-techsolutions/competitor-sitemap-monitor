# ====================================================================
# ENTERPRISE CONTAINERIZATION (DOCKERFILE)
# Ultra-lightweight, zero-dependency, self-healing deployment image
# ====================================================================

# Use the absolute smallest, most secure Python foundation (Alpine Linux)
FROM python:3.11-alpine

# Set zero-lag environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing junk .pyc files
# PYTHONUNBUFFERED: Forces logs to stream instantly without memory buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Create a restricted, non-root system user for world-class security
RUN addgroup -S securitygroup && adduser -S securityuser -G securitygroup

# Set the operational directory
WORKDIR /app

# Pull the core engine into the secure container
COPY monitor.py .

# Lock down file execution permissions to only the security user
RUN chown -R securityuser:securitygroup /app && \
    chmod 700 /app/monitor.py

# Switch off the root user to eliminate privilege escalation vulnerabilities
USER securityuser

# ---------------------------------------------------------
# SELF-HEALING EXECUTION
# If the container crashes, your server's Docker daemon 
# will automatically restart it based on your restart policy.
# ---------------------------------------------------------
CMD ["python", "monitor.py"]
