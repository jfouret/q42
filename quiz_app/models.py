from . import db
import datetime

class QuizSession(db.Model):
    """Represents a single quiz session."""
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Configuration details can be stored as a JSON string or in separate columns
    config = db.Column(db.String, nullable=False) 
    answers = db.relationship('Answer', backref='session', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<QuizSession id={self.id}>"

class Question(db.Model):
    """Represents a single question in the database."""
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String, nullable=False)
    category = db.Column(db.String, nullable=False)
    digest = db.Column(db.String, unique=True, nullable=False) # SHA-256 digest of the question text
    answers = db.relationship('Answer', backref='question', lazy=True)

    def __repr__(self):
        return f"<Question id={self.id} category='{self.category}'>"

class Answer(db.Model):
    """Represents a user's answer to a question within a session."""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('quiz_session.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    
    answer_text = db.Column(db.Text, nullable=True) # Transcribed text
    audio_file_path = db.Column(db.String, nullable=True) # Path to the saved audio file
    duration = db.Column(db.Float, nullable=True) # Duration of the audio recording
    score = db.Column(db.Integer, nullable=True) # Score from 1 to 5
    justification = db.Column(db.Text, nullable=True) # Justification from the LLM
    
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Answer session_id={self.session_id} question_id={self.question_id} score={self.score}>"
