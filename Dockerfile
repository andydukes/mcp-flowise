# Use a Python base image that satisfies the project requirements
FROM python:3.12-slim AS base

# Install the uv package manager
RUN pip install uvx

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install dependencies
RUN uvx sync --frozen --no-dev --no-editable

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables required for running the MCP server
ENV FLOWISE_API_KEY=your_api_key
ENV FLOWISE_API_ENDPOINT=http://localhost:3010

# Define the command to run the app
CMD ["uvx", "--from", "git+https://github.com/andydukes/mcp-flowise", "mcp-flowise"]