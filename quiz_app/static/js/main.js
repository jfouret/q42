document.addEventListener('DOMContentLoaded', () => {
    const nextBtn = document.getElementById('next-btn');
    const nextQuestionForm = document.getElementById('next-question-form');
    const recordingStatus = document.getElementById('recording-status');

    if (nextBtn) {
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
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    // Wait for the server to confirm the upload before moving on.
                    await sendAudioToServer(audioBlob);
                    
                    // Now, submit the form to go to the next question.
                    nextQuestionForm.submit();

                    // Clean up
                    audioChunks = [];
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
                recordingStatus.innerHTML = `
                    <span class="spinner-grow spinner-grow-sm text-danger" role="status"></span>
                    Recording...
                `;
            } catch (err) {
                console.error('Error accessing microphone:', err);
                recordingStatus.textContent = 'Error: Could not access microphone.';
                alert('Could not access the microphone. Please ensure you have given permission.');
            }
        };

        const stopRecordingAndSubmit = () => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                // Disable button and show loading state
                nextBtn.disabled = true;
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

            formData.append('audio', audioBlob, 'recording.wav');
            formData.append('question_id', questionId);

            try {
                const response = await fetch('/submit_answer', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    console.log('Answer submitted successfully');
                } else {
                    console.error('Error submitting answer:', data.error);
                    alert('There was an error submitting your answer.');
                }
            } catch (error) {
                console.error('Fetch error:', error);
                alert('A network error occurred. Please try again.');
            }
        };

        // Start recording as soon as the page loads
        startRecording();

        // Set up the button to stop the current recording and submit
        nextBtn.addEventListener('click', stopRecordingAndSubmit);
    }
});
