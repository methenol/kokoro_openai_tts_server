# Kokoro TTS Server (OpenAI Compatible)

## Overview

This project provides a Text-to-Speech (TTS) web server using the `hexgrad/Kokoro-82M` model via the `kokoro` Python library. It exposes an API compatible with the OpenAI TTS endpoints, allowing easy integration with applications expecting that format.

The server can be run locally using a Python virtual environment or containerized using Docker for straightforward deployment.

## Features

*   **High-Quality TTS:** Leverages the Kokoro model for speech synthesis.
*   **OpenAI API Compatibility:** Provides `/v1/audio/speech` and `/v1/models` endpoints.
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

### Stopping the Server

*   **Local:** Press `Ctrl+C` in the terminal where `python server.py` is running. Deactivate the virtual environment using `deactivate`.
*   **Docker:** Run `docker-compose down` in the project directory.