import os
import io
import streamlit as st
from groq import Groq
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import requests
import base64

# Load environment variables
load_dotenv()

# Set up page config
st.set_page_config(
    page_title="AI Jokes & Stories",
    page_icon="✨",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #1a1a1a 0%, #2c3e50 100%);
        color: #ffffff;
    }
    .stTextInput input, .stSelectbox select {
        background-color: rgba(255,255,255,0.1) !important;
        color: white !important;
    }
    .stButton button {
        background: linear-gradient(45deg, #4CAF50 0%, #2E8B57 100%);
        color: white !important;
        border: none;
        border-radius: 5px;
        padding: 10px 25px;
    }
    .output-box {
        padding: 20px;
        background: rgba(0,0,0,0.3);
        border-radius: 10px;
        margin: 15px 0;
        white-space: pre-line;
    }
    .credit-counter {
        position: fixed;
        bottom: 10px;
        right: 10px;
        background: rgba(0,0,0,0.7);
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize APIs and check quota
def initialize_apis():
    groq_api_key = os.getenv("GROQ_API_KEY") or st.session_state.get('groq_key', '')
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY") or st.session_state.get('el_key', '')
    
    if not groq_api_key or not elevenlabs_api_key:
        st.error("Please provide API keys in sidebar")
        return None, None, None
    
    try:
        groq_client = Groq(api_key=groq_api_key)
        el_client = ElevenLabs(api_key=elevenlabs_api_key)
        
        # Check ElevenLabs quota
        headers = {"xi-api-key": elevenlabs_api_key}
        response = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers)
        if response.status_code == 200:
            data = response.json()
            remaining_credits = data.get("character_limit") - data.get("character_count")
            st.session_state.credits_remaining = remaining_credits
            st.session_state.credits_used = data.get("character_count")
            return groq_client, el_client, remaining_credits
        else:
            st.error(f"Failed to fetch quota: {response.text}")
            return groq_client, el_client, 10000
    except Exception as e:
        st.error(f"API Initialization Error: {str(e)}")
        return None, None, None

# Initialize session state
if 'credits_used' not in st.session_state:
    st.session_state.credits_used = 0
if 'credits_remaining' not in st.session_state:
    st.session_state.credits_remaining = 10000
MAX_CREDITS = 10000

# Voice Settings
VOICE_MAP = {
    "English": {
        "Rachel": ("EXAVITQu4vr4xnSDxMaL", 0.7),
        "Domi": ("AZnzlk1XvdvUeBnXmlld", 0.7)
    },
    "Hindi": {
        "Shweta": ("XB0fDUnXU5powFXDhCwa", 0.7),
        "Prabhat": ("IKne3meq5aSn9XLyUdCD", 0.7)
    }
}

def calculate_credits(text):
    return max(1, len(text) // 10)

def generate_content(client, prompt, max_tokens, temperature=0.7):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Generation Error: {str(e)}")
        return None

def check_and_generate_audio(client, text, voice_id, stability):
    try:
        required_credits = calculate_credits(text)
        if st.session_state.credits_remaining < required_credits:
            st.error(f"Insufficient credits! Required: {required_credits}, Remaining: {st.session_state.credits_remaining}")
            return None, 0, None
        
        audio = client.generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2",
            voice_settings={
                "stability": stability,
                "similarity_boost": 0.8
            }
        )
        
        audio_bytes = io.BytesIO(b"".join(audio))
        used_credits = calculate_credits(text)
        st.session_state.credits_used += used_credits
        st.session_state.credits_remaining -= used_credits
        return audio_bytes, used_credits, text
    except Exception as e:
        error_msg = str(e)
        if "quota_exceeded" in error_msg:
            import re
            match = re.search(r'You have (\d+) credits remaining', error_msg)
            if match:
                remaining = int(match.group(1))
                st.session_state.credits_remaining = remaining
            st.error(f"Quota exceeded: {error_msg}")
        else:
            st.error(f"Audio Error: {error_msg}")
        return None, 0, None

def generate_joke(groq_client, params):
    prompt = f"""Create a {params['length']} {params['language']} {params['style']} joke about {params['topic']}.
    
    Requirements:
    - Style: {params['style']} humor
    - Length: {params['length']} (1-2 lines for short, 3-4 for medium)
    - Must be funny and appropriate
    - Include emoji if suitable"""
    
    return generate_content(groq_client, prompt, max_tokens=150)

def generate_story(groq_client, params):
    prompt = f"""Write a concise {params['language']} story about {params['prompt']}.
    
    Guidelines:
    - 3 short paragraphs max
    - Include character and setting
    - Have a clear beginning, middle, and end
    - Use simple language"""
    
    return generate_content(groq_client, prompt, max_tokens=300)

def play_audio(audio_bytes, text):
    # Convert audio to base64
    audio_base64 = base64.b64encode(audio_bytes.getvalue()).decode('utf-8')
    audio_html = f"""
    <audio autoplay style="display:none;">
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
    </audio>
    <script>
        var audio = document.querySelector('audio');
        audio.onended = function() {{
            var textDiv = document.createElement('div');
            textDiv.className = 'output-box';
            textDiv.innerText = `{text}`;
            document.querySelector('.main').appendChild(textDiv);
        }};
    </script>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def main():
    st.title("✨ AI Jokes & Stories")
    
    groq_client, el_client, initial_credits = initialize_apis()
    if not groq_client or not el_client:
        return

    st.sidebar.markdown(f"""
    <div class="credit-counter">
    Credits Used: {st.session_state.credits_used}/{MAX_CREDITS}<br>
    Credits Remaining: {st.session_state.credits_remaining}
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["😂 Joke Generator", "📖 Story Creator"])

    with tab1:
        st.subheader("Create Your Joke")
        col1, col2 = st.columns(2)
        with col1:
            joke_lang = st.selectbox("Language", ["English", "Hindi"], key="joke_lang")
            joke_voice = st.selectbox("Voice", list(VOICE_MAP[joke_lang].keys()), key="joke_voice")
            joke_style = st.selectbox("Style", ["Pun", "Situational", "Observational"], key="joke_style")
        with col2:
            joke_topic = st.text_input("Topic", "everyday life", key="joke_topic")
            joke_length = st.selectbox("Length", ["Short", "Medium"], key="joke_length")
        
        if st.button("Generate Joke", key="joke_btn"):
            with st.spinner("Crafting your joke..."):
                params = {
                    'language': joke_lang,
                    'style': joke_style,
                    'topic': joke_topic,
                    'length': joke_length
                }
                joke = generate_joke(groq_client, params)
                if joke:
                    if el_client:
                        voice_id, stability = VOICE_MAP[joke_lang][joke_voice]
                        audio, used_credits, generated_text = check_and_generate_audio(el_client, joke, voice_id, stability)
                        if audio:
                            play_audio(audio, generated_text)
                            st.success(f"Used {used_credits} credits")

    with tab2:
        st.subheader("Create Your Story")
        col1, col2 = st.columns(2)
        with col1:
            story_lang = st.selectbox("Language", ["English", "Hindi"], key="story_lang")
            story_voice = st.selectbox("Voice", list(VOICE_MAP[story_lang].keys()), key="story_voice")
        with col2:
            story_prompt = st.text_input("Story Idea", "a mysterious door in the forest", key="story_prompt")
        
        if st.button("Generate Story", key="story_btn"):
            with st.spinner("Writing your story..."):
                params = {
                    'language': story_lang,
                    'prompt': story_prompt
                }
                story = generate_story(groq_client, params)
                if story:
                    if el_client:
                        voice_id, stability = VOICE_MAP[story_lang][story_voice]
                        audio, used_credits, generated_text = check_and_generate_audio(el_client, story, voice_id, stability)
                        if audio:
                            play_audio(audio, generated_text)
                            st.success(f"Used {used_credits} credits")

if __name__ == "__main__":
    main()