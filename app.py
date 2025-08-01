from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import base64
from dotenv import load_dotenv
from groq import Groq
from elevenlabs import ElevenLabs

load_dotenv()

app = Flask(__name__)
CORS(app)

# API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Setup
client = Groq(api_key=GROQ_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVEN_API_KEY)

# Voice IDs
KAREN_VOICE = "exsUS4vynmxd379XN4yO"
SUSAN_VOICE = "tnSpp4vdxKPjI9w0GnoV"

# Character definitions
KAREN = {
    "name": "Karen",
    "voice": KAREN_VOICE,
    "system": (
        "You are Karen, a dramatic woman who is CONVINCED Susan just farted. You are disgusted and outraged. "
        "Keep accusing Susan of farting. Use dramatic, over-the-top reactions. Be petty and childish. "
        "Keep responses short (1-2 sentences). Use simple words. No actions in asterisks."
    )
}

SUSAN = {
    "name": "Susan", 
    "voice": SUSAN_VOICE,
    "system": (
        "You are Susan, an indignant woman who DEFINITELY did NOT fart (but maybe you did). "
        "Deny everything dramatically and blame Karen instead. Be defensive and ridiculous. "
        "Keep responses short (1-2 sentences). Use simple words. No actions in asterisks."
    )
}

# Store conversation history
conversation_history = []

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/start', methods=['POST'])
def start_battle():
    global conversation_history
    conversation_history = []
    
    # Karen's opening line
    opening_line = "OH MY GOD SUSAN! Did you just FART? That's absolutely DISGUSTING!"
    conversation_history.append({"role": "assistant", "content": opening_line})
    
    # Generate audio for Karen
    try:
        audio_generator = elevenlabs_client.text_to_speech.convert(
            text=opening_line,
            voice_id=KAREN_VOICE,
            model_id="eleven_turbo_v2",
            optimize_streaming_latency=3
        )
        
        # Collect audio data
        audio_data = b""
        for chunk in audio_generator:
            audio_data += chunk
        
        # Convert to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return jsonify({
            'status': 'started',
            'speaker': 'karen',
            'message': opening_line,
            'audio': audio_base64
        })
        
    except Exception as e:
        print(f"Audio error: {e}")
        return jsonify({
            'status': 'started',
            'speaker': 'karen',
            'message': opening_line,
            'audio': None
        })

@app.route('/api/next', methods=['POST'])
def get_next_response():
    global conversation_history
    
    data = request.json
    current_speaker = data.get('currentSpeaker', 'susan')
    
    # Determine next speaker
    next_speaker = 'susan' if current_speaker == 'karen' else 'karen'
    speaker_config = SUSAN if next_speaker == 'susan' else KAREN
    
    # Get last message
    last_message = conversation_history[-1]['content'] if conversation_history else ""
    
    # Generate response
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": speaker_config["system"]},
                *conversation_history,
                {"role": "user", "content": last_message}
            ],
            temperature=0.9,
            max_tokens=50
        )
        
        reply = response.choices[0].message.content.strip()
        # Clean up any repeated names
        reply = reply.replace("Karen: ", "").replace("Susan: ", "")
        if reply.startswith("Karen:") or reply.startswith("Susan:"):
            reply = reply.split(":", 1)[1].strip()
        
        # Add to conversation history
        conversation_history.append({"role": "assistant", "content": reply})
        
        # Limit history
        if len(conversation_history) > 16:
            conversation_history = conversation_history[-16:]
        
        # Generate audio
        try:
            voice_id = speaker_config["voice"]
            audio_generator = elevenlabs_client.text_to_speech.convert(
                text=reply,
                voice_id=voice_id,
                model_id="eleven_turbo_v2",
                optimize_streaming_latency=3
            )
            
            audio_data = b""
            for chunk in audio_generator:
                audio_data += chunk
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Estimate duration based on text length
            words = len(reply.split())
            duration = max(2000, words * 300)  # milliseconds
            
            return jsonify({
                'speaker': next_speaker,
                'message': reply,
                'audio': audio_base64,
                'duration': duration
            })
            
        except Exception as e:
            print(f"Audio generation error: {e}")
            return jsonify({
                'speaker': next_speaker,
                'message': reply,
                'audio': None,
                'duration': 3000
            })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'speaker': next_speaker,
            'message': "Error generating response",
            'audio': None,
            'duration': 2000
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # For development
    app.run(debug=True, port=5000)
    
    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:5000 app:app