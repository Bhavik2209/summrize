from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import os
import textwrap
import google.generativeai as genai



os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
  model_name="gemini-pro",
  generation_config=generation_config,
  # safety_settings = Adjust safety settings
  # See https://ai.google.dev/gemini-api/docs/safety-settings
)


from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import requests
import re
import os

def get_video_id(youtube_url):
    """
    Extract the video ID from a YouTube URL.
    Args:
        youtube_url (str): The YouTube URL.
    Returns:
        str: The extracted video ID or None if not found.
    """
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, youtube_url)
    return match.group(1) if match else None

def get_video_title(video_id):
    """
    Get the title of the YouTube video.
    Args:
        video_id (str): The YouTube video ID.
    Returns:
        str: The title of the video or "Unknown" if not found.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        matches = re.findall(r'<title>(.*?)</title>', response.text)
        return matches[0].replace(" - YouTube", "") if matches else "Unknown"
    except requests.RequestException as e:
        print(f"Error fetching video title: {e}")
        return "Unknown"

def download_transcript(video_id):
    """
    Download the transcript and return as a string.
    Args:
        video_id (str): The YouTube video ID.
    Returns:
        str: The transcript text or an empty string if an error occurs.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcripts = {}

        for transcript in transcript_list:
            transcript_text = transcript.fetch()
            formatter = TextFormatter()
            formatted_text = formatter.format_transcript(transcript_text)

            # Remove timecodes and speaker names
            formatted_text = re.sub(r'\[\d+:\d+:\d+\]', '', formatted_text)
            formatted_text = re.sub(r'<\w+>', '', formatted_text)

            transcripts[transcript.language_code] = formatted_text

        return transcripts
    except Exception as e:
        print(f"Error downloading transcript: {e}")
        return ""





# Function to display text as markdown
def to_markdown(text):
    text = text.replace('•', '  *')
    return textwrap.indent(text, '> ', predicate=lambda _: True)


# Initialize the Streamlit app
st.title("Chatbot using Google's GenerativeAI")

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Function to get a response from the GenerativeAI API
def get_gemini_response(prompt):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)

    # Extract the text from the response parts
    try:
        if response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    return to_markdown(part.text)
                else:
                    st.write("No text found in part:", part)
        else:
            st.write("No parts found in the response.")
    except AttributeError as e:
        st.write(f"Error accessing response parts: {e}")

    # Handle the case where response.text might not be directly accessible
    try:
        if hasattr(response, 'text'):
            return to_markdown(response.text)
        else:
            st.write("No direct text found in the response.")
    except ValueError as e:
        st.write(f"Error accessing response text: {e}")

    return "Failed to generate a response."


video_url = st.text_input("Enter the youtube video url")


video_id = get_video_id(video_url)
title = get_video_title(video_id)
transcript = download_transcript(video_id)
# Text input for user prompt
user_input = st.text_input("You: ", "")


prompt = [
        f"the video title is {title} and {transcript}, this is a transcript of the youtube video and u have to understand it and based on this transcript answer the quesion and also answer the user's general question of the transcript topic and if question is out of the context then just write not available, answer in the depth i mean the answrer should be long enough and  here is the question. ,  question : {user_input}"
    ]


response = model.generate_content(prompt)
submit_button = st.button("send")


if submit_button:
    st.write(response.text)