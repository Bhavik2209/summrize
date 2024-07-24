import os
import re
import textwrap
import requests
import streamlit as st
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import google.generativeai as genai

load_dotenv()

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
)

def get_video_id(youtube_url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, youtube_url)
    return match.group(1) if match else None

def get_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        matches = re.findall(r'<title>(.*?)</title>', response.text)
        return matches[0].replace(" - YouTube", "") if matches else "Unknown"
    except requests.RequestException as e:
        return "Unknown"

def get_video_thumbnail(video_id):
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def download_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcripts = {}

        for transcript in transcript_list:
            transcript_text = transcript.fetch()
            formatter = TextFormatter()
            formatted_text = formatter.format_transcript(transcript_text)

            formatted_text = re.sub(r'\[\d+:\d+:\d+\]', '', formatted_text)
            formatted_text = re.sub(r'<\w+>', '', formatted_text)

            transcripts[transcript.language_code] = formatted_text

        return transcripts
    except Exception as e:
        return ""

def to_markdown(text):
    text = text.replace('•', '  *')
    return textwrap.indent(text, '> ', predicate=lambda _: True)

def get_gemini_response(prompt):
    response = model.generate_content(prompt)
    try:
        if response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    return to_markdown(part.text)
                else:
                    return "No text found in part"
        else:
            return "No parts found in the response."
    except AttributeError as e:
        return f"Error accessing response parts: {e}"

    try:
        if hasattr(response, 'text'):
            return to_markdown(response.text)
        else:
            return "No direct text found in the response."
    except ValueError as e:
        return f"Error accessing response text: {e}"

    return "Failed to generate a response."

def format_text_to_html(text):
    text = text.strip().replace('```', '')
    text = text.strip().replace('>', '')
    text = text.strip().replace('html','')
    text = text.strip().replace('* * *','')
    text = text.strip().replace('* *','')
    text = text.strip().replace('*','')
    return text

# Streamlit app
st.title("YouTube Video Analyzer")

# Input YouTube URL
youtube_url = st.text_input("Enter YouTube URL")

if youtube_url:
    video_id = get_video_id(youtube_url)
    title = get_video_title(video_id)
    thumbnail = get_video_thumbnail(video_id)
    transcripts = download_transcript(video_id)

    st.write(f"### Video Title: {title}")
    st.image(thumbnail, width=600)
    
    if transcripts:
        transcript = transcripts.get('en', '')  # Assuming English transcript is available
        

        # Ask a question
        user_input = st.text_input("Ask a question about the video")
        if user_input:
            prompt = f"The video title is '{title}' and this is the transcript of the YouTube video: {transcript}. Based on this transcript, answer the following question in depth. If the question is out of context but if user ask generalized questions related to transcript then give the answer , just write 'not available'. Here is the question: {user_input}"
            response_text = get_gemini_response(prompt)
            formatted_response = format_text_to_html(response_text)
            st.write("### Response:")
            st.write(formatted_response)
    else:
        st.write("No transcript available for this video.")
