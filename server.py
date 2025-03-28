#!/usr/bin/env python3

import os
import io
import json
import logging
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Server config
HOST = "0.0.0.0"
PORT = 8013

# Model and configs
MODEL_ID = "hexgrad/Kokoro-82M"
DEFAULT_LANG_CODE = 'a'  # American English
DEFAULT_VOICE = "af_heart"
SUPPORTED_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]  # Added PCM format

# Global variable for the TTS pipeline
tts_pipeline = None
supported_voices = None
supported_langs = {
    'a': 'American English',
    'b': 'British English',
    'e': 'Spanish',
    'f': 'French',
    'h': 'Hindi',
    'i': 'Italian',
    'p': 'Brazilian Portuguese',
    'j': 'Japanese',
    'z': 'Mandarin Chinese'
}

def get_supported_voices(lang_code=DEFAULT_LANG_CODE):
    """Get the voices supported by Kokoro for the given language."""
    try:
        # Kokoro doesn't provide a direct way to get available voices
        # We'll list the known voices from the documentation and testing
        if lang_code == 'a':  # American English
            voices = [
                "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole",
                "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric",
                "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice",
                "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis"
            ]
        else:
            # For other languages, return a common subset that generally works
            voices = ["en_female_1", "en_male_1", "en_female_2", "en_male_2"]
        
        logger.info(f"Using known voices for language '{lang_code}': {voices}")
        return voices
    except Exception as e:
        logger.error(f"Error getting supported voices: {e}")
        # Return default voice list as fallback
        return ["bm_lewis", "af_heart", "en_female_1", "en_male_1", "en_female_2", "en_male_2", "om_dionysus"]

def load_pipeline(lang_code=DEFAULT_LANG_CODE):
    """Load the Kokoro TTS pipeline."""
    global tts_pipeline, supported_voices
    
    logger.info(f"Loading Kokoro TTS pipeline with language '{lang_code}'...")
    
    try:
        from kokoro import KPipeline
        
        # Initialize the pipeline with the appropriate language
        tts_pipeline = KPipeline(lang_code=lang_code)
        
        # Get supported voices
        supported_voices = get_supported_voices(lang_code)
        
        # Check if GPU is being used
        import torch
        if torch.cuda.is_available():
            logger.info("Using GPU acceleration!")
        else:
            logger.warning("GPU not available, using CPU instead")
            
        logger.info("TTS pipeline loaded successfully!")
        
    except Exception as e:
        logger.error(f"Error loading TTS pipeline: {e}")
        raise

def generate_speech(text, voice=DEFAULT_VOICE, lang_code=DEFAULT_LANG_CODE, response_format="mp3", speed=1.0):
    """Generate speech from text using the Kokoro pipeline."""
    global tts_pipeline, supported_voices
    
    if tts_pipeline is None:
        load_pipeline(lang_code)
    
    try:
        import soundfile as sf
        
        # Generate speech using the pipeline
        generator = tts_pipeline(
            text, 
            voice=voice, 
            speed=speed
        )
        
        # Collect all audio segments
        audio_segments = []
        for i, (graphemes, phonemes, audio) in enumerate(generator):
            audio_segments.append(audio)
        
        # Combine audio segments if there are multiple
        if len(audio_segments) > 1:
            import numpy as np
            combined_audio = np.concatenate(audio_segments)
        else:
            combined_audio = audio_segments[0]
        
        # Get sample rate (should be 24000 for Kokoro)
        sample_rate = 24000
        
        # Convert to specified format
        audio_bytes = convert_audio_format(combined_audio, sample_rate, response_format)
        
        return audio_bytes, response_format
        
    except Exception as e:
        logger.error(f"Error generating speech: {e}")
        logger.error(traceback.format_exc())
        raise

def convert_audio_format(audio_array, sample_rate, format_name):
    """Convert audio array to specified format."""
    import soundfile as sf
    import io
    import numpy as np
    
    # Make sure format is supported
    if format_name not in SUPPORTED_FORMATS:
        format_name = "mp3"  # Default to mp3
    
    audio_io = io.BytesIO()
    
    # Convert PyTorch tensor to NumPy array if needed
    if hasattr(audio_array, 'cpu') and hasattr(audio_array, 'numpy'):
        # It's a PyTorch tensor
        logger.info("Converting PyTorch tensor to NumPy array")
        audio_array = audio_array.cpu().numpy()
    
    if format_name == "mp3":
        import scipy.io.wavfile
        import pydub
        
        # Save as WAV first
        wav_io = io.BytesIO()
        scipy.io.wavfile.write(wav_io, sample_rate, audio_array)
        wav_io.seek(0)
        
        # Convert to MP3
        audio = pydub.AudioSegment.from_wav(wav_io)
        audio.export(audio_io, format="mp3")
    elif format_name == "opus":
        # Save as WAV first then convert to opus
        import scipy.io.wavfile
        import subprocess
        
        # Save as WAV
        wav_io = io.BytesIO()
        scipy.io.wavfile.write(wav_io, sample_rate, audio_array)
        wav_io.seek(0)
        
        # Convert to Opus using ffmpeg
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_wav:
            temp_wav.write(wav_io.getvalue())
            temp_wav.flush()
            
            with tempfile.NamedTemporaryFile(suffix='.opus') as temp_opus:
                subprocess.run(["ffmpeg", "-i", temp_wav.name, "-c:a", "libopus", temp_opus.name, "-y"], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(temp_opus.name, 'rb') as f:
                    audio_io.write(f.read())
    elif format_name == "pcm":
        # PCM format is just the raw samples
        # Convert to int16 PCM format which is common for audio
        pcm_data = (audio_array * 32767).astype(np.int16)
        audio_io.write(pcm_data.tobytes())
    else:
        # Use soundfile for other formats
        sf.write(audio_io, audio_array, sample_rate, format=format_name)
    
    audio_io.seek(0)
    return audio_io.getvalue()

@app.route('/v1/audio/speech', methods=['POST'])
def create_speech():
    """OpenAI compatible TTS endpoint."""
    global supported_voices
    
    try:
        data = request.get_json(silent=True)
        
        # Log the incoming request data for debugging
        logger.info(f"Received request data: {data}")
        
        if data is None:
            logger.error("Invalid JSON payload received")
            return jsonify({"error": "Invalid JSON"}), 400
            
        # Extract parameters
        model = data.get('model', MODEL_ID)
        text = data.get('input')
        voice = data.get('voice', DEFAULT_VOICE)
        response_format = data.get('response_format', 'mp3')
        speed = float(data.get('speed', 1.0))
        
        # Log the parameters
        logger.info(f"Processing request: model={model}, voice={voice}, format={response_format}, speed={speed}")
        
        # Extract language code - default to American English 'a'
        lang_code = DEFAULT_LANG_CODE
        if '.' in voice and len(voice) > 2:
            # If voice contains language code like 'a.bm_lewis'
            parts = voice.split('.', 1)
            if parts[0] in supported_langs:
                lang_code = parts[0]
                voice = parts[1]
        
        logger.info(f"Using language code: {lang_code}, voice: {voice}")
        
        # Validate required parameters
        if not text:
            logger.error("Missing required parameter: input")
            return jsonify({"error": "Missing required parameter: input"}), 400
        
        # Make sure voices are loaded for the language
        if supported_voices is None or tts_pipeline is None or getattr(tts_pipeline, 'lang_code', None) != lang_code:
            logger.info(f"Loading pipeline for language {lang_code}")
            load_pipeline(lang_code)
        
        # Validate voice against known voices
        if voice not in supported_voices:
            logger.error(f"Voice '{voice}' not supported for language '{lang_code}'. Available voices: {supported_voices}")
            return jsonify({"error": f"Voice '{voice}' not supported for language '{lang_code}'. Supported voices: {supported_voices}"}), 400
            
        if response_format not in SUPPORTED_FORMATS:
            logger.error(f"Format '{response_format}' not supported")
            return jsonify({"error": f"Format '{response_format}' not supported. Supported formats: {SUPPORTED_FORMATS}"}), 400
        
        logger.info(f"Generating speech for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
        # Generate speech
        audio_bytes, format_name = generate_speech(
            text=text,
            voice=voice,
            lang_code=lang_code,
            response_format=response_format,
            speed=speed
        )
        
        # Return audio file
        mimetype = f"audio/{format_name}"
        if format_name == "wav":
            mimetype = "audio/wav"
        elif format_name == "pcm":
            mimetype = "audio/pcm"  # Set appropriate MIME type
        
        logger.info(f"Successfully generated audio, returning {len(audio_bytes)} bytes of {format_name} data")
            
        return send_file(
            io.BytesIO(audio_bytes),
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"speech.{format_name}"
        )
        
    except Exception as e:
        logger.error(f"Error in create_speech endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/v1/models', methods=['GET'])
def list_models():
    """OpenAI compatible models listing endpoint."""
    models = [
        {
            "id": MODEL_ID,
            "object": "model",
            "created": 1677610602,
            "owned_by": "user",
            "permission": [],
            "root": MODEL_ID,
            "parent": None
        }
    ]
    
    return jsonify({"object": "list", "data": models})

@app.route('/v1/languages', methods=['GET'])
def list_languages():
    """List available languages for Kokoro."""
    return jsonify({
        "object": "list",
        "data": [
            {"code": code, "name": name} for code, name in supported_langs.items()
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    global supported_voices
    
    # Make sure voices are loaded
    if supported_voices is None:
        supported_voices = get_supported_voices()
    
    return jsonify({
        "status": "ok", 
        "model": MODEL_ID,
        "supported_languages": supported_langs,
        "supported_voices": supported_voices,
        "supported_formats": SUPPORTED_FORMATS
    })

if __name__ == "__main__":
    # Pre-load the pipeline
    try:
        load_pipeline()
    except Exception as e:
        logger.error(f"Failed to load TTS pipeline: {e}")
    
    # Run the server
    logger.info(f"Starting server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)