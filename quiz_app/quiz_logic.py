import json
import hashlib
import os
from . import db
from .models import Question

def load_questions_from_json(directory):
    """
    Loads all .json files from a directory into the database.
    
    This function is idempotent. It calculates a SHA-256 digest of the 
    question text and checks if a question with that digest already 
    exists before adding it to the database.
    """
    if not os.path.exists(directory):
        print(f"Data directory not found: {directory}")
        return

    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    questions_data = json.load(f)
                
                for q_data in questions_data:
                    question_text = q_data.get('question')
                    # Use the filename (without extension) as the category if not in the file
                    category = q_data.get('category', os.path.splitext(filename)[0].replace('_', ' ').title())

                    if not question_text or not category:
                        continue

                    # Create a unique digest for the question to prevent duplicates
                    digest = hashlib.sha256(question_text.encode('utf-8')).hexdigest()

                    # Check if the question already exists
                    existing_question = Question.query.filter_by(digest=digest).first()
                    if not existing_question:
                        new_question = Question(
                            question_text=question_text,
                            category=category,
                            digest=digest
                        )
                        db.session.add(new_question)

            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error loading questions file {filename}: {e}")
                continue
    
    db.session.commit()
    print("Questions loaded and database synchronized.")


def select_questions(categories, num_questions, attempt_multiplier, score_multiplier):
    """
    Selects questions using a weighted random algorithm based on performance.
    Weight = (attempt_multiplier^(mean_attempts - attempts)) * (score_multiplier^(mean_score - score))
    """
    from sqlalchemy import func
    from .models import Answer
    import random
    import math

    # Get all questions for the selected categories
    candidate_questions = Question.query.filter(Question.category.in_(categories)).all()

    if not candidate_questions:
        return []

    # Get stats for all questions to calculate means
    stats = db.session.query(
        Question.id,
        func.count(Answer.id).label('attempts'),
        func.avg(Answer.score).label('avg_score')
    ).join(Answer, Answer.question_id == Question.id, isouter=True)\
     .group_by(Question.id).all()

    # Create a dictionary for easy lookup
    stats_dict = {s.id: {'attempts': s.attempts, 'avg_score': s.avg_score if s.avg_score is not None else 0} for s in stats}

    # Calculate mean attempts and score across all candidates
    total_attempts = sum(s['attempts'] for s in stats_dict.values() if s['attempts'] > 0)
    scored_questions = [s for s in stats_dict.values() if s['attempts'] > 0 and s['avg_score'] is not None]
    
    mean_attempts = total_attempts / len(candidate_questions) if candidate_questions else 0
    mean_score = sum(s['avg_score'] for s in scored_questions) / len(scored_questions) if scored_questions else 3 # Default to 3 if no scores yet

    weights = []
    for q in candidate_questions:
        q_stats = stats_dict.get(q.id, {'attempts': 0, 'avg_score': mean_score})
        
        attempts = q_stats.get('attempts', 0)
        score = q_stats.get('avg_score', mean_score)

        # If a question has never been answered, give it a neutral score weight
        if attempts == 0:
            score = mean_score

        # Calculate weight components
        attempt_weight = math.pow(attempt_multiplier, mean_attempts - attempts)
        # A higher score_multiplier now correctly increases the weight for questions with lower scores.
        score_weight = math.pow(score_multiplier, mean_score - score)
        
        final_weight = attempt_weight * score_weight
        weights.append(final_weight)

    # Ensure we don't request more questions than available
    k = min(num_questions, len(candidate_questions))
    
    # Perform weighted random sampling
    # The 'choices' function allows for replacement, so we'll loop to get unique questions.
    selected_questions = []
    population = list(candidate_questions)
    
    # Guard against empty population
    if not population:
        return []

    # Use weighted random choice to select unique questions
    while len(selected_questions) < k and population:
        chosen = random.choices(population, weights=weights, k=1)[0]
        selected_questions.append(chosen)
        
        # Remove the chosen question and its weight to ensure uniqueness
        idx = population.index(chosen)
        population.pop(idx)
        weights.pop(idx)

    return selected_questions
