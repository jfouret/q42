import os
from mistralai import Mistral

# Retrieve the API key from environment variables
# retrie from dotenvapi_key = ""

# Specify model
model = "voxtral-mini-latest"

# Initialize the Mistral client
client = Mistral(api_key=api_key)

# If local audio, upload and retrieve the signed url
with open("/home/jfouret/Downloads/question_63.webm", "rb") as f:
    uploaded_audio = client.files.upload(
      file={
          "content": f,
          "file_name": f.name
      },
      purpose="audio"
    )

print(uploaded_audio.id)

signed_url = client.files.get_signed_url(file_id=uploaded_audio.id)

# Get the transcription
transcription_response = client.audio.transcriptions.complete(
    model=model,
    file_url=signed_url.url,
    ## language="en"
)

# Print the content of the response
print(transcription_response.text)
