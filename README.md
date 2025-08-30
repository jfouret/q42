# AI Voice Quizzer

This is a Flask-based web application for taking voice-based quizzes. It records your answers, transcribes them, and uses AI to evaluate your performance.

## Project Setup

### 1. Prerequisites

- Python 3.10+
- `uv` (a fast Python package installer and resolver)
- `ffmpeg` (for audio processing)

On Debian/Ubuntu, you can install `ffmpeg` with:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

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

Copy the `.env.example` file to `.env` and fill in your API keys and secrets:

```bash
cp .env.example .env
# Now, edit the .env file with your keys
```

**Note:** The application requires valid API keys for Deepgram and OpenRouter, a `SECRET_KEY` for Flask sessions, a `JWT_SECRET_KEY` for authentication, and an `AUTH_PASSWORD` for logging in.

## Running for Development

Activate the virtual environment and run the Flask application:

```bash
source .venv/bin/activate
uv run python app.py
```

You can now access the application at **http://127.0.0.1:5000**.

## How to Deploy

For production, it is recommended to use a production-ready WSGI server like Gunicorn.

1.  **Set Environment Variables:** Ensure all variables in your `.env` file are set correctly for your production environment. It is crucial to use strong, randomly generated secrets for `SECRET_KEY` and `JWT_SECRET_KEY`.

2.  **Run with Gunicorn:**
    You can start the application with Gunicorn using the following command:
    ```bash
    gunicorn --bind 0.0.0.0:8000 "quiz_app:create_app()"
    ```
    This will start the application on port 8000. You should place a reverse proxy like Nginx or Caddy in front of it to handle HTTPS and serve static files.

## Authentication

This application is protected by a simple password-based authentication system. When you first access the application, you will be redirected to a login page. Enter the password defined in the `AUTH_PASSWORD` environment variable to gain access.

## Data Persistence

The application stores data in several locations within the repository. When deploying, you should ensure these locations are backed up or mounted as persistent volumes if you are using containers.

-   **Questions:** `/data/questions/` - Contains the JSON files with quiz questions.
-   **User Uploads:** `/quiz_app/uploads/` - Stores the audio recordings of user answers, organized by session ID.
-   **Generated Audio:** `/quiz_app/static/audio/` - Caches the text-to-speech audio files for questions.
-   **Database:** `/database/quiz.db` - The SQLite database file containing all session and answer data.

## Question Database

The application loads questions from JSON files located in the directory specified by the `QUESTIONS_DIR` environment variable (default: `data/questions`).

Each JSON file should contain a list of question objects. The format for each object is as follows:

```json
[
  {
    "question": "What is the capital of France?",
    "category": "Geography"
  },
  {
    "question": "Who wrote 'To Kill a Mockingbird'?",
    "category": "Literature"
  }
]
```

-   `question`: The text of the question.
-   `category`: The category of the question. If not provided, the filename (without the `.json` extension) will be used as the category.

You can add your own `.json` files to the `data/questions` directory to expand the question pool.
