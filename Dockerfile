FROM python:3.11-slim

# 1. Install system dependencies
# 'build-essential' is needed for compiling some python extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Poetry
# We use 1.6.1 as requested, though upgrading to 1.8+ is often safer for new locking features
RUN pip install poetry==1.6.1

# 3. Configure Poetry: No virtualenvs inside Docker
RUN poetry config virtualenvs.create false

WORKDIR /code

# 4. Copy configuration files first (for Docker caching)
COPY ./pyproject.toml ./README.md ./poetry.lock* ./

# 5. Copy local packages (Optional - note the *)
# This prevents the build from failing if you don't have a local packages folder
COPY ./packages* ./packages/

# 6. Install dependencies
# We install dependencies BEFORE copying the app code.
# This ensures that changing your code doesn't force a re-download of all libraries.
RUN poetry install --no-interaction --no-ansi --no-root

# 7. Copy the application code
COPY ./app ./app

# 8. Install the project itself (if it's a package)
RUN poetry install --no-interaction --no-ansi

EXPOSE 8080

# 9. Start the server
# Use array format for better signal handling
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]