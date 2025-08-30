document.addEventListener('DOMContentLoaded', () => {
    const themeSwitcher = document.getElementById('theme-switcher');
    const htmlElement = document.documentElement;

    const setTheme = (theme) => {
        htmlElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
    };

    const toggleTheme = () => {
        const currentTheme = htmlElement.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
    };

    if (themeSwitcher) {
        themeSwitcher.addEventListener('click', toggleTheme);
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        setTheme(savedTheme);
    }

    const nextBtn = document.getElementById('next-btn');
    const skipBtn = document.getElementById('skip-btn');
    const nextQuestionForm = document.getElementById('next-question-form');
    const recordingStatus = document.getElementById('recording-status');
    const questionAudio = document.getElementById('question-audio');
    const showQuestionBtn = document.getElementById('show-question-btn');
    const questionText = document.getElementById('question-text');
    const startQuestionBtn = document.getElementById('start-question-btn');

    let mediaRecorder;
    let audioChunks = [];

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                if (audioChunks.length > 0) {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await sendAudioToServer(audioBlob);
                }
                nextQuestionForm.submit();
                audioChunks = [];
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            recordingStatus.innerHTML = `
                <span class="spinner-grow spinner-grow-sm text-danger" role="status"></span>
                Recording...
            `;
            nextBtn.disabled = false;
        } catch (err) {
            console.error('Error accessing microphone:', err);
            recordingStatus.textContent = 'Error: Could not access microphone.';
            alert('Could not access the microphone. Please ensure you have given permission.');
        }
    };

    const stopRecordingAndSubmit = () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            nextBtn.disabled = true;
            if(skipBtn) skipBtn.disabled = true;
            nextBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                Saving...
            `;
            recordingStatus.textContent = 'Finalizing recording...';
            mediaRecorder.stop();
        }
    };

    const sendAudioToServer = async (audioBlob) => {
        const formData = new FormData();
        const questionId = document.querySelector('.card').dataset.questionId;

        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('question_id', questionId);

        try {
            const response = await fetch('/submit_answer', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (!data.success) {
                console.error('Error submitting answer:', data.error);
                alert('There was an error submitting your answer.');
            }
        } catch (error) {
            console.error('Fetch error:', error);
            alert('A network error occurred. Please try again.');
        }
    };

    if (startQuestionBtn) {
        startQuestionBtn.addEventListener('click', () => {
            questionAudio.play();
            startQuestionBtn.style.display = 'none';
            showQuestionBtn.classList.remove('d-none');
        });
    }

    if (questionAudio) {
        questionAudio.addEventListener('ended', startRecording);
        questionAudio.addEventListener('error', () => {
            recordingStatus.textContent = 'Error playing question audio. Starting recording.';
            startRecording();
        });
    }

    if (showQuestionBtn) {
        showQuestionBtn.addEventListener('click', () => {
            questionText.classList.remove('d-none');
            showQuestionBtn.style.display = 'none';
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', stopRecordingAndSubmit);
    }

    if (skipBtn) {
        skipBtn.addEventListener('click', () => {
            skipBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;

            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                audioChunks = [];
                mediaRecorder.stop();
            }

            fetch('/skip_question', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.url) {
                    window.location.href = data.url;
                } else {
                    skipBtn.disabled = false;
                    if (nextBtn) nextBtn.disabled = false;
                    alert('Error skipping question.');
                }
            })
            .catch(error => {
                console.error('Error skipping question:', error);
                skipBtn.disabled = false;
                if (nextBtn) nextBtn.disabled = false;
            });
        });
    }
});
