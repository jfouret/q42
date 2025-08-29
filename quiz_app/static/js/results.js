document.addEventListener('DOMContentLoaded', () => {
    // Nothing to run on load for now, all actions are user-triggered.
});

function showLoading(answerId) {
    const card = document.getElementById(`answer-card-${answerId}`);
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    card.appendChild(loadingOverlay);
}

function hideLoading(answerId) {
    const card = document.getElementById(`answer-card-${answerId}`);
    const overlay = card.querySelector('.loading-overlay');
    if (overlay) {
        card.removeChild(overlay);
    }
}

function updateAnswerUI(answerId, data) {
    if (data.answer_text) {
        document.getElementById(`answer-text-${answerId}`).textContent = data.answer_text;
    }
    if (data.score !== undefined) {
        const scoreSpan = document.getElementById(`answer-score-${answerId}`);
        let stars = '';
        for (let i = 1; i <= 5; i++) {
            stars += `<span class="star ${i <= data.score ? 'filled' : ''}">★</span>`;
        }
        scoreSpan.innerHTML = `${stars} (${data.score}/5)`;
    }
    if (data.justification) {
        // Note: This assumes the justification is plain text.
        // If it contains markdown, a more complex solution is needed to render it.
        document.querySelector(`#answer-justification-${answerId} p`).textContent = data.justification;
    }
}

async function handleFetch(url, answerId) {
    showLoading(answerId);
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();
        if (data.success) {
            updateAnswerUI(answerId, data);
        } else {
            alert(`Error: ${data.error || 'An unknown error occurred.'}`);
        }
    } catch (error) {
        console.error('Fetch error:', error);
        alert('A network error occurred. Please try again.');
    } finally {
        hideLoading(answerId);
    }
}

function retranscribe(answerId) {
    handleFetch(`/re-transcribe/${answerId}`, answerId);
}

function reevaluate(answerId) {
    handleFetch(`/re-evaluate/${answerId}`, answerId);
}

async function saveTranscription(answerId) {
    const textarea = document.getElementById(`editTextarea-${answerId}`);
    const newText = textarea.value;
    const modalInstance = bootstrap.Modal.getInstance(document.getElementById(`editModal-${answerId}`));

    showLoading(answerId);
    modalInstance.hide();

    try {
        const response = await fetch(`/edit-transcription/${answerId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: newText })
        });
        const data = await response.json();
        if (data.success) {
            updateAnswerUI(answerId, data);
        } else {
            alert(`Error: ${data.error || 'An unknown error occurred.'}`);
        }
    } catch (error) {
        console.error('Fetch error:', error);
        alert('A network error occurred. Please try again.');
    } finally {
        hideLoading(answerId);
    }
}

// Add some CSS for the loading overlay
const style = document.createElement('style');
style.innerHTML = `
.loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10;
}
`;
document.head.appendChild(style);
