from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, current_app, make_response, send_file
from .models import Question, QuizSession, Answer
from .quiz_logic import select_questions
from .stt import transcribe_audio
from .evaluation import evaluate_answer
from .audio_utils import get_audio_duration
from .tts import generate_speech_file
from .translate import get_translated_question, translate_question, save_translated_question, get_translated_question_path
from . import db
import os
import concurrent.futures
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Displays and saves user preferences, like the STT provider."""
    if request.method == 'POST':
        stt_provider = request.form.get('stt_provider')
        if stt_provider in ['deepgram', 'mistral']:
            session['stt_provider'] = stt_provider

        alt_language = request.form.get('alt_language')
        if alt_language in ['en', 'fr']:
            session['alt_language'] = alt_language

        session['enforce_alt_language'] = 'enforce_alt_language' in request.form
        
        return redirect(url_for('main.settings'))

    current_provider = session.get('stt_provider', 'mistral')
    return render_template('settings.html', current_provider=current_provider)

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

    # Check if weighting is enabled, otherwise use a neutral value of 1.0
    enable_attempt_weighting = request.form.get('enable_attempt_weighting') == 'on'
    enable_score_weighting = request.form.get('enable_score_weighting') == 'on'

    attempt_multiplier = float(request.form.get('attempt_multiplier', 1.5)) if enable_attempt_weighting else 1.0
    score_multiplier = float(request.form.get('score_multiplier', 1.5)) if enable_score_weighting else 1.0

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
    
    text_dir = os.path.join(current_app.static_folder, 'text')
    return render_template('quiz.html', question=question, current_index=current_index, total_questions=len(question_ids), get_translated_question=lambda qid: get_translated_question(qid, text_dir))

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
    # Note: uploads are stored relative to the application's root path
    session_upload_dir = os.path.join(current_app.root_path, 'uploads', str(session_id))
    os.makedirs(session_upload_dir, exist_ok=True)

    # Create a secure filename and the full absolute path for saving
    filename = f"question_{question_id}.webm"
    absolute_path = os.path.join(session_upload_dir, filename)
    
    # Save the file
    audio_file.save(absolute_path)
    audio_file.close()

    # Generate the relative path to store in the database
    # This path is relative to the project root (one level above app root)
    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    relative_path = os.path.relpath(absolute_path, project_root)

    # Create a new Answer record with the relative file path
    new_answer = Answer(
        session_id=session_id,
        question_id=question_id,
        audio_file_path=relative_path
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

@main_bp.route('/skip_question', methods=['POST'])
def skip_question():
    """Skips the current question without saving an answer."""
    if 'quiz_session_id' not in session:
        return jsonify({'error': 'No active quiz session'}), 400

    # Just advance the question index
    current_index = session.get('current_question_index', 0)
    session['current_question_index'] = current_index + 1

    question_ids = session.get('question_ids', [])
    if session['current_question_index'] >= len(question_ids):
        return jsonify({'status': 'finished', 'url': url_for('main.results')})
    else:
        return jsonify({'status': 'ok', 'url': url_for('main.quiz')})

def _process_session_answers(session_id):
    """Helper function to run the AI pipeline for all unprocessed answers in a session."""
    answers_to_process = Answer.query.filter_by(session_id=session_id, answer_text=None).all()

    if not answers_to_process:
        return

    # Get the provider from the session before entering the thread pool
    stt_provider = session.get('stt_provider', 'mistral')

    eval_config = {
        'DEEPGRAM_API_KEY': current_app.config.get('DEEPGRAM_API_KEY'),
        'DEEPGRAM_MODEL': current_app.config.get('DEEPGRAM_MODEL'),
        'DEEPGRAM_LANGUAGE': current_app.config.get('DEEPGRAM_LANGUAGE'),
        'MISTRAL_API_KEY': current_app.config.get('MISTRAL_API_KEY'),
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

    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    tasks = []
    for answer in answers_to_process:
        absolute_audio_path = os.path.join(project_root, answer.audio_file_path)
        tasks.append({
            "answer_id": answer.id,
            "audio_path": absolute_audio_path,
            "question_text": answer.question.question_text,
            "category": answer.question.category,
            "stt_provider": stt_provider  # Pass the provider to the task
        })

    def process_single_answer(task_data):
        try:
            duration = get_audio_duration(task_data["audio_path"])
            # Pass the provider to the transcription function
            transcribed_text = transcribe_audio(
                task_data["audio_path"], 
                eval_config, 
                provider=task_data["stt_provider"]
            )
            evaluation_result = evaluate_answer(
                task_data["question_text"], transcribed_text, task_data["category"], eval_config, duration
            )
            return {
                "answer_id": task_data["answer_id"], "duration": duration,
                "answer_text": transcribed_text, "score": evaluation_result.get("score"),
                "justification": evaluation_result.get("justification")
            }
        except Exception as e:
            print(f"Error processing answer {task_data['answer_id']}: {e}")
            return {"answer_id": task_data['answer_id'], "justification": f"An error occurred: {e}"}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_single_answer, tasks))

    for result in results:
        answer = Answer.query.get(result["answer_id"])
        if answer:
            answer.duration = result.get("duration")
            answer.answer_text = result.get("answer_text")
            answer.score = result.get("score")
            answer.justification = result.get("justification")
    
    db.session.commit()

@main_bp.route('/results')
def results():
    """Processes all answers for the completed session and displays the results."""
    session_id = session.get('quiz_session_id')
    if not session_id:
        return redirect(url_for('main.index'))

    _process_session_answers(session_id)
    
    final_answers = Answer.query.filter_by(session_id=session_id).order_by(Answer.id).all()
    response = make_response(render_template('results.html', answers=final_answers, session_id=session_id))
    
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
    
    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    absolute_path = os.path.join(project_root, answer.audio_file_path)
    return send_file(absolute_path)

@main_bp.route('/sessions')
def sessions_list():
    """Displays a list of all past quiz sessions with aggregated stats."""
    from sqlalchemy import func, desc
    from sqlalchemy.orm import aliased

    # Alias for a subquery to get the last score
    last_answer_subquery = db.session.query(
        Answer.session_id,
        func.max(Answer.timestamp).label('last_timestamp')
    ).group_by(Answer.session_id).subquery()

    last_answer = aliased(Answer)

    sessions_with_stats = db.session.query(
        QuizSession,
        func.count(Answer.id).label('num_questions'),
        func.avg(Answer.score).label('avg_score'),
        func.max(Answer.score).label('max_score'),
        func.avg(Answer.duration).label('avg_duration')
    ).outerjoin(Answer, QuizSession.id == Answer.session_id)\
     .group_by(QuizSession.id)\
     .order_by(desc(QuizSession.start_time))\
     .all()

    # The query returns tuples, so we need to combine them
    sessions = []
    for session_obj, num_q, avg_s, max_s, avg_d in sessions_with_stats:
        session_obj.num_questions = num_q
        session_obj.avg_score = avg_s
        session_obj.max_score = max_s
        session_obj.avg_duration = avg_d
        sessions.append(session_obj)

    return render_template('sessions.html', sessions=sessions)

@main_bp.route('/session/<int:session_id>')
def session_detail(session_id):
    """Displays the detailed results for a specific session."""
    quiz_session = QuizSession.query.get_or_404(session_id)
    return render_template('results.html', answers=quiz_session.answers, session_id=session_id)

def _get_eval_config():
    """Helper to get the full evaluation configuration from the app config."""
    return {
        'DEEPGRAM_API_KEY': current_app.config.get('DEEPGRAM_API_KEY'),
        'DEEPGRAM_MODEL': current_app.config.get('DEEPGRAM_MODEL'),
        'DEEPGRAM_LANGUAGE': current_app.config.get('DEEPGRAM_LANGUAGE'),
        'MISTRAL_API_KEY': current_app.config.get('MISTRAL_API_KEY'),
        'DEEPGRAM_MAX_RETRIES': current_app.config.get('DEEPGRAM_MAX_RETRIES', 3),
        'DEEPGRAM_RETRY_DELAY': current_app.config.get('DEEPGRAM_RETRY_DELAY', 1),
        'OPENROUTER_API_KEY': current_app.config.get('OPENROUTER_API_KEY'),
        'REASONING_MODEL': current_app.config.get('REASONING_MODEL'),
        'REASONING_TEMPERATURE': current_app.config.get('REASONING_TEMPERATURE'),
        'REASONING_TOP_K': current_app.config.get('REASONING_TOP_K'),
        'STRUCTURED_OUTPUT_MODEL': current_app.config.get('STRUCTURED_OUTPUT_MODEL'),
        'STRUCTURED_OUTPUT_TEMPERATURE': current_app.config.get('STRUCTURED_OUTPUT_TEMPERATURE'),
        'STRUCTURED_OUTPUT_TOP_K': current_app.config.get('STRUCTURED_OUTPUT_TOP_K'),
        'OPENROUTER_MAX_RETRIES': current_app.config.get('OPENROUTER_MAX_RETRIES', 3),
        'REASONING_CONTEXT_USER': current_app.config.get('REASONING_CONTEXT_USER'),
        'REASONING_CONTEXT_SYSTEM': current_app.config.get('REASONING_CONTEXT_SYSTEM'),
        'STRUCTURED_CONTEXT_USER': current_app.config.get('STRUCTURED_CONTEXT_USER'),
        'STRUCTURED_CONTEXT_SYSTEM': current_app.config.get('STRUCTURED_CONTEXT_SYSTEM'),
    }

def _reevaluate_and_save(answer, duration=None):
    """Helper function to re-evaluate an answer and save it."""
    eval_config = _get_eval_config()
    
    # If duration is not provided, try to get it from the answer object
    if duration is None:
        duration = answer.duration

    evaluation_result = evaluate_answer(
        answer.question.question_text,
        answer.answer_text,
        answer.question.category,
        eval_config,
        duration
    )
    answer.score = evaluation_result.get("score")
    answer.justification = evaluation_result.get("justification")
    db.session.commit()
    return answer

@main_bp.route('/re-transcribe/<int:answer_id>', methods=['POST'])
def re_transcribe(answer_id):
    """Re-runs transcription and evaluation for a single answer."""
    answer = Answer.query.get_or_404(answer_id)
    eval_config = _get_eval_config()
    
    if not answer.audio_file_path:
        return jsonify({"success": False, "error": "No audio file available for this answer."}), 400

    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    absolute_path = os.path.join(project_root, answer.audio_file_path)

    # Get the provider from the session
    stt_provider = session.get('stt_provider', 'mistral')

    # Re-transcribe, passing the provider
    transcribed_text = transcribe_audio(absolute_path, eval_config, provider=stt_provider)
    answer.answer_text = transcribed_text
    
    # Re-evaluate
    updated_answer = _reevaluate_and_save(answer, duration=answer.duration)

    return jsonify({
        "success": True,
        "answer_text": updated_answer.answer_text,
        "score": updated_answer.score,
        "justification": updated_answer.justification
    })

@main_bp.route('/re-evaluate/<int:answer_id>', methods=['POST'])
def re_evaluate(answer_id):
    """Re-runs evaluation for a single answer."""
    answer = Answer.query.get_or_404(answer_id)
    
    if not answer.answer_text:
        return jsonify({"success": False, "error": "No transcription available to evaluate."}), 400

    updated_answer = _reevaluate_and_save(answer)

    return jsonify({
        "success": True,
        "score": updated_answer.score,
        "justification": updated_answer.justification
    })

@main_bp.route('/edit-transcription/<int:answer_id>', methods=['POST'])
def edit_transcription(answer_id):
    """Updates the transcription and re-evaluates the answer."""
    answer = Answer.query.get_or_404(answer_id)
    new_text = request.json.get('text')

    if new_text is None:
        return jsonify({"success": False, "error": "No text provided."}), 400

    answer.answer_text = new_text
    updated_answer = _reevaluate_and_save(answer, duration=answer.duration)

    return jsonify({
        "success": True,
        "answer_text": updated_answer.answer_text,
        "score": updated_answer.score,
        "justification": updated_answer.justification
    })

@main_bp.route('/reprocess_session/<int:session_id>', methods=['POST'])
def reprocess_session(session_id):
    """Clears and re-runs the evaluation for all answers in a session."""
    answers_to_reprocess = Answer.query.filter_by(session_id=session_id).all()
    for answer in answers_to_reprocess:
        answer.answer_text = None
        answer.score = None
        answer.justification = None
        answer.duration = None
    db.session.commit()

    # Now, trigger the processing and redirect to the results page
    _process_session_answers(session_id)
    return redirect(url_for('main.session_detail', session_id=session_id))

@main_bp.route('/questions')
def questions_list():
    """Displays a list of all questions and their stats."""
    from sqlalchemy import func, desc, case
    from sqlalchemy.orm import aliased

    show_unanswered = request.args.get('show_unanswered')

    # Subquery to find the last answer for each question
    last_answer_subquery = db.session.query(
        Answer.question_id,
        func.max(Answer.timestamp).label('last_timestamp')
    ).group_by(Answer.question_id).subquery()

    last_answer = aliased(Answer)

    # Base query for question stats
    question_stats_sq = db.session.query(
        Question.id.label('question_id'),
        func.count(Answer.id).label('times_answered'),
        func.avg(Answer.score).label('avg_score'),
        func.max(Answer.score).label('max_score')
    ).join(Answer, Question.id == Answer.question_id)\
     .group_by(Question.id).subquery()

    # Main query combining question info with stats
    query = db.session.query(
        Question,
        question_stats_sq.c.times_answered,
        question_stats_sq.c.avg_score,
        question_stats_sq.c.max_score,
        func.avg(Answer.duration).label('avg_duration'),
        func.min(Answer.duration).label('min_duration'),
        last_answer.duration.label('last_duration'),
        last_answer.score.label('last_score')
    ).outerjoin(question_stats_sq, Question.id == question_stats_sq.c.question_id)\
     .outerjoin(Answer, Question.id == Answer.question_id)\
     .outerjoin(last_answer_subquery, Question.id == last_answer_subquery.c.question_id)\
     .outerjoin(last_answer, (last_answer.question_id == last_answer_subquery.c.question_id) & (last_answer.timestamp == last_answer_subquery.c.last_timestamp))\
     .group_by(Question.id)

    if not show_unanswered:
        query = query.filter(question_stats_sq.c.times_answered > 0)

    questions_with_stats = query.order_by(Question.id).all()
     
    questions = []
    for row in questions_with_stats:
        q_obj = row[0]
        q_obj.times_answered = row[1] or 0
        q_obj.avg_score = row[2]
        q_obj.max_score = row[3]
        q_obj.avg_duration = row[4]
        q_obj.min_duration = row[5]
        q_obj.last_duration = row[6]
        q_obj.last_score = row[7]
        questions.append(q_obj)

    # Calculate overall metrics
    answered_once = db.session.query(func.count(question_stats_sq.c.question_id)).filter(question_stats_sq.c.times_answered >= 1).scalar()
    answered_twice = db.session.query(func.count(question_stats_sq.c.question_id)).filter(question_stats_sq.c.times_answered >= 2).scalar()
    
    answered_twice_low_score = db.session.query(func.count(question_stats_sq.c.question_id)).filter(
        question_stats_sq.c.times_answered >= 2,
        question_stats_sq.c.avg_score < 4
    ).scalar()

    max_score_high = db.session.query(func.count(question_stats_sq.c.question_id)).filter(
        question_stats_sq.c.max_score >= 4
    ).scalar()

    metrics = {
        'answered_once': answered_once,
        'answered_twice': answered_twice,
        'answered_twice_low_score': answered_twice_low_score,
        'max_score_high': max_score_high
    }
        
    return render_template('questions.html', questions=questions, metrics=metrics)

@main_bp.route('/categories')
def categories_summary():
    """Displays a summary of performance by category."""
    from sqlalchemy import func, desc, case

    last_n_sessions = request.args.get('last_n_sessions', type=int)

    # Subquery to get question-level stats
    question_stats_sq = db.session.query(
        Question.id.label('question_id'),
        Question.category,
        func.count(Answer.id).label('times_answered'),
        func.avg(Answer.score).label('avg_score'),
        func.max(Answer.score).label('max_score')
    ).join(Answer, Question.id == Answer.question_id)

    if last_n_sessions:
        latest_session_ids = [s.id for s in db.session.query(QuizSession.id).order_by(desc(QuizSession.start_time)).limit(last_n_sessions).all()]
        question_stats_sq = question_stats_sq.filter(Answer.session_id.in_(latest_session_ids))
    
    question_stats_sq = question_stats_sq.group_by(Question.id).subquery()

    # Main query to aggregate by category
    category_stats_query = db.session.query(
        question_stats_sq.c.category,
        func.avg(question_stats_sq.c.avg_score).label('avg_score'),
        func.max(question_stats_sq.c.max_score).label('max_score'),
        func.count(question_stats_sq.c.question_id).label('num_questions'),
        func.sum(case((question_stats_sq.c.max_score >= 4, 1), else_=0)).label('ge_4_5'),
        func.sum(case((question_stats_sq.c.times_answered > 2, 1), else_=0)).label('n_gt_2'),
        func.sum(case(((question_stats_sq.c.times_answered > 2) & (question_stats_sq.c.avg_score < 4), 1), else_=0)).label('n_gt_2_lt_4')
    ).group_by(question_stats_sq.c.category).order_by(question_stats_sq.c.category)

    category_stats = category_stats_query.all()

    return render_template('categories.html', category_stats=category_stats, last_n_sessions=last_n_sessions)

@main_bp.route('/reset_database', methods=['POST'])
def reset_database():
    """Drops all data, recreates tables, and reloads questions."""
    db.drop_all()
    db.create_all()
    from .quiz_logic import load_questions_from_json
    questions_dir = current_app.config.get('QUESTIONS_DIR')
    if questions_dir:
        load_questions_from_json(questions_dir)
    return redirect(url_for('main.index'))

@main_bp.route('/generate-audio', methods=['POST'])
def generate_audio():
    """Generates audio files for all questions."""
    questions = Question.query.all()
    created_count = 0
    skipped_count = 0
    failed_count = 0

    token = current_app.config.get('SPEECHIFY_API_TOKEN')
    audio_dir = current_app.config.get('TTS_AUDIO_DIR')
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)


    for question in questions:
        file_path, status = generate_speech_file(question.id, question.question_text, token, audio_dir)
        if status == 'created':
            created_count += 1
        elif status == 'skipped':
            skipped_count += 1
        else:
            failed_count += 1
    
    return jsonify({
        'success': True, 
        'message': f'Audio generation complete. Created: {created_count}, Skipped: {skipped_count}, Failed: {failed_count}'
    })
@main_bp.route('/generate-alt-audio', methods=['POST'])
def generate_alt_audio():
    """Generates audio files for all questions in the alternative language."""
    questions = Question.query.all()
    created_count = 0
    skipped_count = 0
    failed_count = 0

    alt_language = session.get('alt_language', 'en')
    api_key = current_app.config.get('OPENROUTER_API_KEY')
    text_dir = os.path.join(current_app.static_folder, 'text')
    token = current_app.config.get('SPEECHIFY_API_TOKEN')
    audio_dir = current_app.config.get('TTS_AUDIO_DIR')
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = []
        for q in questions:
            if not os.path.exists(get_translated_question_path(q.id, text_dir)):
                futures.append(executor.submit(translate_question, q.question_text, api_key, alt_language))

        for future in concurrent.futures.as_completed(futures):
            try:
                translated_text = future.result()
                # Find the question associated with the translated text
                for q in questions:
                    if q.question_text == future.arg:
                        question = q
                        break
                save_translated_question(question.id, translated_text, text_dir)
            except Exception as exc:
                print(f'A question generated an exception: {exc}')
                failed_count += 1
    # Second pass for audio generation for existing translations
    for q in questions:
        translated_text = get_translated_question(q.id, text_dir)
        if translated_text:
            file_path_alt, status_alt = generate_speech_file(q.id, translated_text, token, audio_dir, is_alt=True)
            if status_alt == 'created':
                created_count += 1
            elif status_alt == 'skipped':
                skipped_count += 1
            else:
                failed_count += 1


    return jsonify({
        'success': True, 
        'message': f'Alternate audio generation complete. Created: {created_count}, Skipped: {skipped_count}, Failed: {failed_count}'
    })

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

@main_bp.route('/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
    """Deletes a session and all its associated answers."""
    session_to_delete = QuizSession.query.get_or_404(session_id)
    db.session.delete(session_to_delete)
    db.session.commit()
    return redirect(url_for('main.sessions_list'))

@main_bp.route('/question/<int:question_id>')
def question_detail(question_id):
    """Displays a detailed view of a single question and all its answers."""
    from sqlalchemy import func, desc

    question = Question.query.get_or_404(question_id)
    
    # Query for all answers to this question, ordered by timestamp
    answers = Answer.query.filter_by(question_id=question_id).order_by(desc(Answer.timestamp)).all()
    
    # Calculate statistics
    num_attempts = len(answers)
    if num_attempts > 0:
        avg_score = sum(a.score for a in answers if a.score is not None) / num_attempts
        last_answer = answers[0]
        last_score = last_answer.score
        avg_duration = sum(a.duration for a in answers if a.duration is not None) / num_attempts
        last_duration = last_answer.duration
    else:
        avg_score = 0
        last_score = None
        avg_duration = 0
        last_duration = None

    stats = {
        'num_attempts': num_attempts,
        'avg_score': avg_score,
        'last_score': last_score,
        'avg_duration': avg_duration,
        'last_duration': last_duration,
    }

    return render_template('question_detail.html', question=question, answers=answers, stats=stats)

@main_bp.route('/start_single_question_quiz', methods=['POST'])
def start_single_question_quiz():
    """Starts a new quiz with only one question."""
    question_id = request.form.get('question_id')
    if not question_id:
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)

    # Create a new quiz session
    new_session = QuizSession(config=f"Single question: {question_id}")
    db.session.add(new_session)
    db.session.commit()

    # Store quiz info in the user's session
    session['quiz_session_id'] = new_session.id
    session['question_ids'] = [question.id]
    session['current_question_index'] = 0

    return redirect(url_for('main.quiz'))
