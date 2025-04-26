# Use a Python base image that satisfies the project requirements
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory in the container


# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --locked

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables required for running the MCP server
ENV FLOWISE_API_KEY=Eq8Nu-hPsTqNaYudT71HLllG8B0sx_oM6h64Q9wOC8Q
ENV FLOWISE_API_ENDPOINT=http://localhost:3010

# Define the command to run the app
CMD ["uvx", "--from", "git+https://github.com/andydukes/mcp-flowise", "mcp-flowise"]