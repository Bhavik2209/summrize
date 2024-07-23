import os
import re
import textwrap
import requests
from dotenv import load_dotenv
from django.shortcuts import render
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

import html

import re

def format_text_to_html(text):
    # Remove code block markers and clean up extra spaces
    text = text.strip().replace('```', '')
    text = text.strip().replace('>', '')
    text = text.strip().replace('html','')
    text = text.strip().replace('* * *','')
    text = text.strip().replace('* *','')
    text = text.strip().replace('*','')

    

    return text




def index(request):
    context = {"show_analytics": True}

    if request.method == "POST" and "url" in request.POST:
        youtube_url = request.POST.get('url')
        video_id = get_video_id(youtube_url)
        title = get_video_title(video_id)
        thumbnail = get_video_thumbnail(video_id)
        transcript = download_transcript(video_id)

        context.update({
            "video_id": video_id,
            "video_title": title,
            "video_thumbnail": thumbnail,
            "transcript": transcript,
        })

    return render(request, 'index.html', context)

def ask_question(request):
    context = {"show_analytics": True}

    if request.method == "POST":
        video_id = request.POST.get('video_id')
        transcript = request.POST.get('transcript')
        user_input = request.POST.get('user_input')

        prompt = [
            f"the video title is {video_id} and {transcript}, this is a transcript of the youtube video and you have to understand it and based on this transcript answer the question and if user ask generalized questions answer the user's general question of the transcript topic and if the question is out of context then just write not available. Answer in depth. Here is the question: {user_input}"
        ]

        response_text = get_gemini_response(prompt)
       

        context.update({
            "response_text": response_text,
            "video_id": video_id,
            "transcript": transcript,
            "video_title": get_video_title(video_id),
            "video_thumbnail": get_video_thumbnail(video_id),
        })

    return render(request, 'index.html', context)
