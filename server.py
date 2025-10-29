#!/usr/bin/env python3

import os
import io
import json
import logging
import traceback
from pathlib import Path
from typing import List, Tuple, Dict, Any
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
VOICE_REPO = os.environ.get("KOKORO_VOICE_REPO", "hexgrad/Kokoro-82M")
DEFAULT_LANG_CODE = 'a'  # American English
DEFAULT_VOICE = "af_heart"
SUPPORTED_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]  # Added PCM format

# Global variable for the TTS pipeline
tts_pipeline = None
supported_voices = None
voice_pack_cache = {}  # Cache for loaded voice packs
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
        return [
            "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole",
            "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric",
            "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
            "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george",
            "bm_lewis", "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
            "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi", "zm_yunjian", "zm_yunxi",
            "zm_yunxia", "zm_yunyang", "ef_dora", "em_alex", "em_santa", "ff_siwis",
            "hf_alpha", "hf_beta", "hm_omega", "hm_psi", "if_sara", "im_nicola",
            "pf_dora", "pm_alex", "pm_santa"
        ]

def is_blend_expression(voice: str) -> bool:
    """Check if a voice string is a blend expression."""
    return ',' in voice or (':' in voice and '.' not in voice.split(':')[0])

def parse_blend_expression(voice_expr: str) -> Tuple[str, List[Tuple[str, float]]]:
    """
    Parse a blend expression like 'af_heart:90,am_adam:10' or 'a.af_heart:70,am_adam:30'.
    
    Returns:
        Tuple of (lang_code, list of (voice_name, weight) tuples)
    
    Raises:
        ValueError: If the expression is malformed
    """
    # Validate input
    if not voice_expr or not voice_expr.strip():
        raise ValueError("Empty blend expression")
    
    try:
        items = [item.strip() for item in voice_expr.split(',')]
        if not items or all(not item for item in items):
            raise ValueError("Empty blend expression")
        
        # Parse first item to extract language code
        first_item = items[0]
        if not first_item:
            raise ValueError("Empty blend expression")
        
        lang_code = DEFAULT_LANG_CODE
        
        # Check if first item has explicit language prefix (e.g., 'a.af_heart:70')
        if '.' in first_item:
            lang_part, rest = first_item.split('.', 1)
            if lang_part in supported_langs:
                lang_code = lang_part
                first_item = rest
                items[0] = rest
        else:
            # Extract language from first character of first voice name
            voice_name = first_item.split(':')[0] if ':' in first_item else first_item
            if voice_name and voice_name[0] in supported_langs:
                lang_code = voice_name[0]
        
        # Parse all items to get (name, weight) tuples
        parsed_items = []
        cross_language_voices = []
        
        for item in items:
            if not item:
                raise ValueError("Empty voice name in blend expression")
            
            if ':' in item:
                parts = item.rsplit(':', 1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid format in '{item}'")
                    
                voice_name = parts[0].strip()
                weight_str = parts[1].strip()
                
                if not voice_name:
                    raise ValueError("Empty voice name in blend expression")
                if not weight_str:
                    raise ValueError(f"Empty weight for voice '{voice_name}'")
                
                # Parse weight (can be percentage or number)
                if weight_str.endswith('%'):
                    weight = float(weight_str[:-1]) / 100.0
                else:
                    weight = float(weight_str)
                    
                if weight <= 0:
                    raise ValueError(f"Weight must be positive, got {weight}")
            else:
                voice_name = item.strip()
                weight = 1.0
            
            # Check if voice has different language prefix
            if voice_name and voice_name[0] in supported_langs and voice_name[0] != lang_code:
                cross_language_voices.append(voice_name)
            
            parsed_items.append((voice_name, weight))
        
        # Warn if cross-language blending detected
        if cross_language_voices:
            logger.warning(f"Cross-language blending detected. Base language: {lang_code}, "
                         f"other voices: {cross_language_voices}")
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weight for _, weight in parsed_items)
        if total_weight <= 0:
            raise ValueError("Total weight must be positive")
        
        normalized_items = [(name, weight / total_weight) for name, weight in parsed_items]
        
        return lang_code, normalized_items
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Malformed blend expression '{voice_expr}': {str(e)}")

def load_voice_pack(voice_name: str) -> Any:
    """
    Load a voice pack from Hugging Face Hub.
    
    Args:
        voice_name: Name of the voice (e.g., 'af_heart')
    
    Returns:
        Loaded voice pack (list of tensors)
    
    Raises:
        ValueError: If voice pack cannot be loaded
    """
    global voice_pack_cache
    
    # Check cache first
    if voice_name in voice_pack_cache:
        logger.info(f"Using cached voice pack for '{voice_name}'")
        return voice_pack_cache[voice_name]
    
    try:
        import torch
        from huggingface_hub import hf_hub_download
        
        # Download the voice pack file
        logger.info(f"Downloading voice pack for '{voice_name}' from {VOICE_REPO}")
        voice_path = hf_hub_download(
            repo_id=VOICE_REPO,
            filename=f"voices/{voice_name}.pt"
        )
        
        # Load the voice pack
        voice_pack = torch.load(voice_path, map_location='cpu')
        
        # Cache it
        voice_pack_cache[voice_name] = voice_pack
        logger.info(f"Successfully loaded and cached voice pack for '{voice_name}'")
        
        return voice_pack
        
    except Exception as e:
        logger.error(f"Failed to load voice pack '{voice_name}': {e}")
        raise ValueError(f"unknown voice '{voice_name}'")

def blend_voice_packs(voice_weights: List[Tuple[str, float]]) -> Any:
    """
    Blend multiple voice packs with given weights.
    
    Args:
        voice_weights: List of (voice_name, weight) tuples
    
    Returns:
        Blended voice pack (list of tensors)
    
    Raises:
        ValueError: If voice packs cannot be loaded or blended
    """
    import torch
    
    logger.info(f"Blending voices: {voice_weights}")
    
    # Validate input
    if not voice_weights:
        raise ValueError("No voices specified for blending")
    
    # Load all voice packs
    packs = []
    for voice_name, weight in voice_weights:
        pack = load_voice_pack(voice_name)
        packs.append((pack, weight))
    
    # Determine minimum length across all packs
    min_length = min(len(pack) for pack, _ in packs)
    logger.info(f"Blending {len(packs)} voice packs, using minimum length: {min_length}")
    
    # Blend each position in the pack
    blended_pack = []
    for i in range(min_length):
        # Compute weighted sum of tensors at position i
        blended_tensor = None
        for pack, weight in packs:
            tensor = pack[i]
            if blended_tensor is None:
                blended_tensor = tensor * weight
            else:
                blended_tensor = blended_tensor + tensor * weight
        blended_pack.append(blended_tensor)
    
    logger.info(f"Successfully blended voice pack with {len(blended_pack)} style vectors")
    return blended_pack

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
        
        # Check if voice is a blend expression
        if is_blend_expression(voice):
            logger.info(f"Detected blend expression: {voice}")
            blend_lang, voice_weights = parse_blend_expression(voice)
            blended_pack = blend_voice_packs(voice_weights)
            voice_arg = blended_pack
            
            # Use the language from the blend expression
            if blend_lang != lang_code:
                logger.info(f"Switching language from {lang_code} to {blend_lang} based on blend expression")
                lang_code = blend_lang
                if tts_pipeline is None or getattr(tts_pipeline, 'lang_code', None) != lang_code:
                    load_pipeline(lang_code)
        else:
            voice_arg = voice
        
        # Generate speech using the pipeline
        generator = tts_pipeline(
            text, 
            voice=voice_arg, 
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
        original_voice = voice
        
        # Check if it's a blend expression first
        if is_blend_expression(voice):
            try:
                lang_code, _ = parse_blend_expression(voice)
                logger.info(f"Blend expression detected, using language code: {lang_code}")
            except ValueError as e:
                logger.error(f"Invalid blend expression: {e}")
                return jsonify({"error": str(e)}), 400
        elif '.' in voice and len(voice) > 2:
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
        
        # Validate voice - skip validation for blend expressions as they're validated during parsing
        if not is_blend_expression(voice) and voice not in supported_voices:
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
        "supported_formats": SUPPORTED_FORMATS,
        "supports_blended_voices": True
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