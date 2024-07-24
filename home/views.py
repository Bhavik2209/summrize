import os
import re
import textwrap
import requests
from dotenv import load_dotenv
from django.shortcuts import render
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import transformers
import torch

load_dotenv()

# Define the Llama model pipeline
model_id = "unsloth/llama-3-8b-Instruct-bnb-4bit"

pipeline = transformers.pipeline(
    "text-generation",
    model=model_id,
    model_kwargs={
        "torch_dtype": torch.float16,
        "quantization_config": {"load_in_4bit": True},
        "low_cpu_mem_usage": True,
    },
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

def get_llama_response(prompt):
    terminators = [
        pipeline.tokenizer.eos_token_id,
        pipeline.tokenizer.convert_tokens_to_ids("")
    ]

    outputs = pipeline(
        prompt,
        max_new_tokens=256,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.6,
        top_p=0.9,
    )

    return outputs[0]["generated_text"][len(prompt):]

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

        response_text = get_llama_response(prompt)

        context.update({
            "response_text": response_text,
            "video_id": video_id,
            "transcript": transcript,
            "video_title": get_video_title(video_id),
            "video_thumbnail": get_video_thumbnail(video_id),
        })

    return render(request, 'index.html', context)
