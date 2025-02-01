# Use a Python base image that satisfies the project requirements
FROM python:3.12-slim AS base

# Install the uv package manager
RUN apt-get update && apt-get install -y build-essential && pip install uv

#RUN pip install uv

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev --no-editable

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables required for running the MCP server
ENV FLOWISE_API_KEY=HsPt77beDamAw8_ZukdqsNk1P4XRRDXY55HnLNF9MAs
ENV FLOWISE_API_ENDPOINT=http://localhost:3006

# Define the command to run the app
CMD ["uv", "--from", "git+https://github.com/andydukes/mcp-flowise", "mcp-flowise"]