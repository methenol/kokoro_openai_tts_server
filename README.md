# Kokoro TTS Server (OpenAI Compatible)

## Overview

This project provides a Text-to-Speech (TTS) web server using the `hexgrad/Kokoro-82M` model via the `kokoro` Python library. It exposes an API compatible with the OpenAI TTS endpoints, allowing easy integration with applications expecting that format.

The server can be run locally using a Python virtual environment or containerized using Docker for straightforward deployment.

## Features

*   **High-Quality TTS:** Leverages the Kokoro model for speech synthesis.
*   **OpenAI API Compatibility:** Provides `/v1/audio/speech` and `/v1/models` endpoints.
*   **Blended Voices:** Support for weighted blending of multiple voices (e.g., `af_heart:90,am_adam:10`).
*   **Multiple Languages:** Supports various languages including:
    *   American English (`a`)
    *   British English (`b`)
    *   Spanish (`e`)
    *   French (`f`)
    *   Hindi (`h`)
    *   Italian (`i`)
    *   Brazilian Portuguese (`p`)
    *   Japanese (`j`)
    *   Mandarin Chinese (`z`)
*   **Multiple Voices:** Offers a selection of voices for supported languages (primarily English). Default voice is `af_heart`.
*   **Various Audio Formats:** Supports output in `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`.
*   **Configurable Speed:** Allows adjusting the speech rate.
*   **Dockerized:** Easy to build and run using Docker and Docker Compose.
*   **GPU Acceleration:** Configured in `docker-compose.yml` to utilize NVIDIA GPUs for faster inference (CPU fallback available).
*   **Additional Endpoints:** Includes `/health` for status checks and `/v1/languages` to list supported languages.

## Installation & Running

You can run the server either locally using Python or within a Docker container.

### Option 1: Local Installation (Python `.venv`)

#### Prerequisites

*   Python 3.10+
*   `pip` (Python package installer)
*   `ffmpeg` (Required for audio conversion, especially MP3/Opus. Installation varies by OS - see [ffmpeg website](https://ffmpeg.org/download.html))
*   `espeak-ng` (Required by Kokoro. Installation varies by OS - search your package manager for `espeak-ng`)
*   (Optional) CUDA-enabled GPU and compatible PyTorch installation for GPU acceleration.

#### Steps

1.  **Clone the repository (if applicable):**
    ```bash
    # git clone <repository-url>
    # cd <repository-directory>
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *   *Note:* If you have a CUDA-enabled GPU, ensure your PyTorch installation (`torch` in `requirements.txt`) matches your CUDA version for GPU acceleration. You might need to install a specific PyTorch version manually (see [PyTorch website](https://pytorch.org/get-started/locally/)).
4.  **Run the server:**
    ```bash
    python server.py
    ```
    *   The server will start and listen on `http://0.0.0.0:8013`.

### Option 2: Running with Docker

#### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)
*   (Optional but Recommended for Performance) [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) if using an NVIDIA GPU.

#### Steps

1.  **Clone the repository (if applicable):**
    ```bash
    # git clone <repository-url>
    # cd <repository-directory>
    ```
2.  **Build and run the container using Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
    *   This command builds the Docker image based on the `Dockerfile` and starts the `kokoro-tts` service defined in `docker-compose.yml`.
    *   The `-d` flag runs the container in detached mode (in the background).
    *   The service will be accessible on port `8013`.

## Usage

The server exposes several endpoints, accessible via `http://localhost:8013` (or the appropriate host if running remotely):

*   `POST /v1/audio/speech`: Generates speech audio.
*   `GET /v1/models`: Lists the available TTS model.
*   `GET /v1/languages`: Lists supported languages and their codes.
*   `GET /health`: Provides a health check and server configuration details.

### Example: Generating Speech with `curl`

You can test the speech generation endpoint using `curl`. Replace `"Your text here"` with the desired input text. You can also change the `voice`, `response_format`, and `speed`. The default voice is `af_heart`.

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "Hello world! This is a test of the Kokoro TTS server.",
           "voice": "a.af_heart", # Format: <lang_code>.<voice_name> (e.g., 'a' for American English)
           "response_format": "mp3",
           "speed": 1.0
         }' \
     --output speech.mp3

echo "Audio saved to speech.mp3"
```

*   **Note on Voices:** To specify a language other than the default (American English), prefix the voice name with the language code and a dot (e.g., `b.bm_lewis` for British English). If you omit the prefix (e.g., `af_heart`), the server will use the default American English (`a`). Check the `/health` or `/v1/languages` endpoints for available codes and voices.

### Blended Voices

The server supports **blended voices**, which allow you to create a weighted combination of multiple voices. This feature enables you to create unique voice characteristics by mixing different voices together.

#### Syntax

Blended voices use a comma-separated list of voice names with optional weights:

```
<voice1>:<weight1>,<voice2>:<weight2>,...
```

**Examples:**

*   **With explicit weights:**
    ```bash
    curl -X POST http://localhost:8013/v1/audio/speech \
         -H "Content-Type: application/json" \
         -d '{
               "model": "hexgrad/Kokoro-82M",
               "input": "Hello! This is a blended voice.",
               "voice": "af_heart:90,am_adam:10",
               "response_format": "mp3"
             }' \
         --output blended_speech.mp3
    ```
    This creates a voice that is 90% `af_heart` and 10% `am_adam`.

*   **Equal weights (no explicit weights):**
    ```bash
    curl -X POST http://localhost:8013/v1/audio/speech \
         -H "Content-Type: application/json" \
         -d '{
               "model": "hexgrad/Kokoro-82M",
               "input": "This blend uses equal weights.",
               "voice": "af_heart,af_bella",
               "response_format": "mp3"
             }' \
         --output equal_blend.mp3
    ```
    This creates a 50/50 blend of `af_heart` and `af_bella`.

*   **With percentage weights:**
    ```bash
    curl -X POST http://localhost:8013/v1/audio/speech \
         -H "Content-Type: application/json" \
         -d '{
               "model": "hexgrad/Kokoro-82M",
               "input": "Using percentage notation.",
               "voice": "bf_emma:25%,af_heart:75%",
               "response_format": "mp3"
             }' \
         --output percentage_blend.mp3
    ```

*   **With explicit language prefix:**
    ```bash
    curl -X POST http://localhost:8013/v1/audio/speech \
         -H "Content-Type: application/json" \
         -d '{
               "model": "hexgrad/Kokoro-82M",
               "input": "Blended British English voices.",
               "voice": "b.bf_alice:60,bf_emma:40",
               "response_format": "mp3"
             }' \
         --output british_blend.mp3
    ```

*   **Multiple voices:**
    ```bash
    curl -X POST http://localhost:8013/v1/audio/speech \
         -H "Content-Type: application/json" \
         -d '{
               "model": "hexgrad/Kokoro-82M",
               "input": "Blending three voices together.",
               "voice": "af_heart:50,am_adam:30,af_bella:20",
               "response_format": "mp3"
             }' \
         --output triple_blend.mp3
    ```

#### Notes

*   **Language Detection:** The language is automatically determined from the first voice in the blend expression. If the first voice has an explicit language prefix (e.g., `b.bf_alice`), that language will be used. Otherwise, the language is inferred from the first character of the first voice name.
*   **Weight Normalization:** Weights are automatically normalized to sum to 1.0, so you can use any positive numbers.
*   **Voice Availability:** All voices in a blend expression must exist in the configured voice repository (default: `hexgrad/Kokoro-82M`).
*   **Cross-Language Blending:** While technically possible, blending voices from different languages may produce unexpected results. The server will log a warning if this is detected.
*   **Configuration:** You can set a custom voice repository using the `KOKORO_VOICE_REPO` environment variable.

#### How It Works

When you specify a blended voice:

1.  The server downloads each voice pack file (`voices/<name>.pt`) from the Hugging Face repository.
2.  Voice packs are cached in memory to avoid repeated downloads.
3.  The server computes a weighted average of the voice style vectors across all specified voices.
4.  The blended voice pack is passed to the Kokoro TTS engine to generate speech.

This approach allows for smooth voice transitions and unique voice characteristics that aren't available with single voices alone.

### Stopping the Server

*   **Local:** Press `Ctrl+C` in the terminal where `python server.py` is running. Deactivate the virtual environment using `deactivate`.
*   **Docker:** Run `docker-compose down` in the project directory.