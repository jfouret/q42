from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, current_app, make_response, send_file
from .models import Question, QuizSession, Answer
from .quiz_logic import select_questions
from .stt import transcribe_audio
from .evaluation import evaluate_answer
from .audio_utils import get_audio_duration
from . import db
import os
import concurrent.futures
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Homepage: Displays the quiz configuration form."""
    categories = [c[0] for c in db.session.query(Question.category).distinct()]
    return render_template('index.html', categories=categories)

@main_bp.route('/start_quiz', methods=['POST'])
def start_quiz():
    """Starts a new quiz session based on form data."""
    num_questions = int(request.form.get('num_questions', 5))
    categories = request.form.getlist('categories')
    attempt_multiplier = float(request.form.get('attempt_multiplier', 1.2))
    score_multiplier = float(request.form.get('score_multiplier', 0.8))

    if not categories:
        # Handle case where no categories are selected
        return redirect(url_for('main.index'))

    questions = select_questions(
        categories=categories,
        num_questions=num_questions,
        attempt_multiplier=attempt_multiplier,
        score_multiplier=score_multiplier
    )

    # Create a new quiz session in the database
    new_session = QuizSession(config=str(request.form.to_dict()))
    db.session.add(new_session)
    db.session.commit()

    # Store quiz info in the user's session
    session['quiz_session_id'] = new_session.id
    session['question_ids'] = [q.id for q in questions]
    session['current_question_index'] = 0

    return redirect(url_for('main.quiz'))

@main_bp.route('/quiz')
def quiz():
    """Displays the current quiz question."""
    if 'quiz_session_id' not in session:
        return redirect(url_for('main.index'))

    question_ids = session.get('question_ids', [])
    current_index = session.get('current_question_index', 0)

    if current_index >= len(question_ids):
        # Quiz is finished
        return redirect(url_for('main.results'))

    question_id = question_ids[current_index]
    question = Question.query.get_or_404(question_id)
    
    return render_template('quiz.html', question=question, current_index=current_index, total_questions=len(question_ids))

@main_bp.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Saves the audio answer and triggers the evaluation pipeline."""
    if 'quiz_session_id' not in session:
        return jsonify({'error': 'No active quiz session'}), 400

    audio_file = request.files.get('audio')
    question_id = request.form.get('question_id')
    session_id = session['quiz_session_id']

    if not audio_file or not question_id:
        return jsonify({'error': 'Missing audio file or question ID'}), 400

    # Create a directory for the session if it doesn't exist
    session_upload_dir = os.path.join(current_app.root_path, 'uploads', str(session_id))
    os.makedirs(session_upload_dir, exist_ok=True)

    # Create a secure filename
    filename = f"question_{question_id}.wav"
    file_path = os.path.join(session_upload_dir, filename)
    
    # Save the file
    audio_file.save(file_path)

    # Create a new Answer record with just the file path
    # The transcription and evaluation will happen on the results page
    new_answer = Answer(
        session_id=session_id,
        question_id=question_id,
        audio_file_path=file_path
    )
    db.session.add(new_answer)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Answer saved.'})


@main_bp.route('/next_question', methods=['POST'])
def next_question():
    """Moves to the next question in the quiz."""
    if 'quiz_session_id' not in session:
        return redirect(url_for('main.index'))

    current_index = session.get('current_question_index', 0)
    session['current_question_index'] = current_index + 1
    
    return redirect(url_for('main.quiz'))

@main_bp.route('/results')
def results():
    """
    Processes all answers for the completed session and displays the results.
    """
    session_id = session.get('quiz_session_id')
    if not session_id:
        return redirect(url_for('main.index'))

    # Fetch all answers for the session that haven't been processed yet
    answers_to_process = Answer.query.filter_by(session_id=session_id, answer_text=None).all()

    # Create a snapshot of the necessary config to pass to the threads
    eval_config = {
        'DEEPGRAM_API_KEY': current_app.config.get('DEEPGRAM_API_KEY'),
        'DEEPGRAM_MODEL': current_app.config.get('DEEPGRAM_MODEL'),
        'DEEPGRAM_LANGUAGE': current_app.config.get('DEEPGRAM_LANGUAGE'),
        'OPENROUTER_API_KEY': current_app.config.get('OPENROUTER_API_KEY'),
        'REASONING_MODEL': current_app.config.get('REASONING_MODEL'),
        'REASONING_TEMPERATURE': current_app.config.get('REASONING_TEMPERATURE'),
        'REASONING_TOP_K': current_app.config.get('REASONING_TOP_K'),
        'STRUCTURED_OUTPUT_MODEL': current_app.config.get('STRUCTURED_OUTPUT_MODEL'),
        'STRUCTURED_OUTPUT_TEMPERATURE': current_app.config.get('STRUCTURED_OUTPUT_TEMPERATURE'),
        'STRUCTURED_OUTPUT_TOP_K': current_app.config.get('STRUCTURED_OUTPUT_TOP_K'),
        'REASONING_CONTEXT_USER': current_app.config.get('REASONING_CONTEXT_USER'),
        'REASONING_CONTEXT_SYSTEM': current_app.config.get('REASONING_CONTEXT_SYSTEM'),
        'STRUCTURED_CONTEXT_USER': current_app.config.get('STRUCTURED_CONTEXT_USER'),
        'STRUCTURED_CONTEXT_SYSTEM': current_app.config.get('STRUCTURED_CONTEXT_SYSTEM'),
    }

    # Prepare a list of dictionaries with the data needed for processing
    tasks = []
    for answer in answers_to_process:
        tasks.append({
            "answer_id": answer.id,
            "audio_path": answer.audio_file_path,
            "question_text": answer.question.question_text,
            "category": answer.question.category
        })

    def process_single_answer(task_data):
        """Processes one answer: gets duration, transcribes, and evaluates."""
        try:
            duration = get_audio_duration(task_data["audio_path"])
            transcribed_text = transcribe_audio(task_data["audio_path"], eval_config)
            evaluation_result = evaluate_answer(
                task_data["question_text"], 
                transcribed_text, 
                task_data["category"], 
                eval_config
            )
            return {
                "answer_id": task_data["answer_id"],
                "duration": duration,
                "answer_text": transcribed_text,
                "score": evaluation_result.get("score"),
                "justification": evaluation_result.get("justification")
            }
        except Exception as e:
            print(f"Error processing answer {answer.id}: {e}")
            return {
                "answer_id": answer.id,
                "justification": f"An error occurred during processing: {e}"
            }

    # Process all answers in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_single_answer, tasks))

    # Update the database with the results from the parallel processing
    for result in results:
        answer = Answer.query.get(result["answer_id"])
        if answer:
            answer.duration = result.get("duration")
            answer.answer_text = result.get("answer_text")
            answer.score = result.get("score")
            answer.justification = result.get("justification")
    
    db.session.commit()

    # Fetch all answers for the session again to display
    final_answers = Answer.query.filter_by(session_id=session_id).order_by(Answer.id).all()
    
    # Render the results page first
    response = make_response(render_template('results.html', answers=final_answers, session_id=session_id))

    # Clear the session after the response has been prepared
    session.pop('quiz_session_id', None)
    session.pop('question_ids', None)
    session.pop('current_question_index', None)
    
    return response

@main_bp.route('/uploads/<int:session_id>/<int:answer_id>')
def serve_audio(session_id, answer_id):
    """Serves the audio file for a specific answer."""
    answer = Answer.query.get_or_404(answer_id)
    if answer.session_id != session_id:
        return "Not Found", 404
    return send_file(answer.audio_file_path)

@main_bp.route('/sessions')
def sessions_list():
    """Displays a list of all past quiz sessions."""
    sessions = QuizSession.query.order_by(QuizSession.start_time.desc()).all()
    return render_template('sessions.html', sessions=sessions)

@main_bp.route('/session/<int:session_id>')
def session_detail(session_id):
    """Displays the detailed results for a specific session."""
    session = QuizSession.query.get_or_404(session_id)
    return render_template('results.html', answers=session.answers, session_id=session.id)

@main_bp.route('/export_session/<int:session_id>')
def export_session(session_id):
    """Exports a session's data to a JSON file."""
    session = QuizSession.query.get_or_404(session_id)
    
    session_data = {
        "session_id": session.id,
        "start_time": session.start_time.isoformat(),
        "config": session.config,
        "answers": []
    }

    for answer in session.answers:
        session_data["answers"].append({
            "question_id": answer.question_id,
            "question_text": answer.question.question_text,
            "category": answer.question.category,
            "answer_text": answer.answer_text,
            "score": answer.score,
            "justification": answer.justification,
            "duration": answer.duration,
            "timestamp": answer.timestamp.isoformat()
        })

    response = jsonify(session_data)
    response.headers['Content-Disposition'] = f'attachment; filename=session_{session_id}.json'
    return response
