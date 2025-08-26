# AI Voice Quizzer

This is a Flask-based web application for taking voice-based quizzes. It records your answers, transcribes them, and uses AI to evaluate your performance.

## Project Setup

### 1. Prerequisites

- Python 3.10+
- `uv` (a fast Python package installer and resolver)

### 2. Installation

First, create and activate a virtual environment using `uv`:

```bash
uv venv
source .venv/bin/activate
```

Then, install the required Python packages:

```bash
uv pip install -r requirements.txt
```

### 3. Environment Variables

Copy the `.env.example` file to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Now, edit the .env file with your keys
```

**Note:** The application will not work without valid API keys for Deepgram and OpenRouter.

## Running the Application

Activate the virtual environment and run the Flask application:

```bash
source .venv/bin/activate
uv run python app.py
```

You can now access the application at **http://127.0.0.1:5000**.

## Stopping the Application

- To stop the Flask app, press `Ctrl+C` in the terminal.
