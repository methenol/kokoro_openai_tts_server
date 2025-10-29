# Blended Voices Examples

This document provides practical examples for using the blended voice feature of the Kokoro TTS server.

## Basic Usage

### Example 1: Simple Blend with Explicit Weights

Blend `af_heart` (90%) with `am_adam` (10%):

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "This is a test of blended voices with explicit weights.",
           "voice": "af_heart:90,am_adam:10",
           "response_format": "mp3"
         }' \
     --output blend_90_10.mp3
```

### Example 2: Equal Weight Blend

Blend two voices with equal weights (50/50):

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "This blend uses equal weights for both voices.",
           "voice": "af_heart,af_bella",
           "response_format": "mp3"
         }' \
     --output blend_equal.mp3
```

### Example 3: Using Percentage Notation

You can use percentages instead of decimals:

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "This example uses percentage notation for weights.",
           "voice": "bf_emma:25%,af_heart:75%",
           "response_format": "mp3"
         }' \
     --output blend_percentage.mp3
```

### Example 4: Multiple Voice Blend

Blend three or more voices:

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "Blending three different voices together creates unique characteristics.",
           "voice": "af_heart:50,am_adam:30,af_bella:20",
           "response_format": "mp3"
         }' \
     --output blend_triple.mp3
```

### Example 5: With Explicit Language Prefix

Specify language explicitly for British English voices:

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "This uses British English voices with explicit language specification.",
           "voice": "b.bf_alice:60,bf_emma:40",
           "response_format": "mp3"
         }' \
     --output blend_british.mp3
```

## Use Cases

### Creating Unique Character Voices

For game development or audiobook narration, you can create unique character voices by blending:

```bash
# A wise elder character (deeper male voice with a hint of warmth)
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "Listen carefully, young one, for I shall tell you a tale of old.",
           "voice": "am_michael:70,am_adam:30",
           "response_format": "mp3",
           "speed": 0.9
         }' \
     --output character_elder.mp3

# A friendly shopkeeper (bright and welcoming)
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "Welcome to my shop! What can I get for you today?",
           "voice": "af_sarah:60,af_heart:40",
           "response_format": "mp3",
           "speed": 1.1
         }' \
     --output character_shopkeeper.mp3
```

### Gender-Neutral Voices

Create a more androgynous or gender-neutral voice:

```bash
curl -X POST http://localhost:8013/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{
           "model": "hexgrad/Kokoro-82M",
           "input": "This voice has characteristics from both traditionally male and female voices.",
           "voice": "af_heart:50,am_adam:50",
           "response_format": "mp3"
         }' \
     --output voice_neutral.mp3
```

## Notes

- **Weight Normalization**: The server automatically normalizes weights, so `af_heart:2,am_adam:3` produces the same result as `af_heart:40,am_adam:60`.

- **Language Consistency**: While you can blend voices from different languages, it's recommended to stick to voices from the same language for best results.

- **Performance**: Voice packs are cached after first download, so subsequent requests using the same voices will be faster.

- **Voice Availability**: You can check available voices by calling the `/health` endpoint:
  ```bash
  curl http://localhost:8013/health | jq '.supported_voices'
  ```

## Programmatic Usage (Python Example)

```python
import requests

def generate_blended_speech(text, voice_blend, output_file):
    """Generate speech with blended voices."""
    response = requests.post(
        "http://localhost:8013/v1/audio/speech",
        json={
            "model": "hexgrad/Kokoro-82M",
            "input": text,
            "voice": voice_blend,
            "response_format": "mp3"
        }
    )
    
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        print(f"Audio saved to {output_file}")
    else:
        print(f"Error: {response.json()}")

# Example usage
generate_blended_speech(
    "Hello from Python!",
    "af_heart:70,am_adam:30",
    "python_blend.mp3"
)
```

## C# Example (As Mentioned in Issue)

```csharp
using System.Net.Http;
using System.Text;
using System.Text.Json;

public class VoiceConfig
{
    public string Engine { get; set; }
    public string Voice { get; set; }
    public int Port { get; set; }
}

// Single voice
var singleVoice = new VoiceConfig 
{ 
    Engine = "KoKoro", 
    Voice = "am_adam", 
    Port = 8013 
};

// Blended voice - NOW SUPPORTED!
var blendedVoice = new VoiceConfig 
{ 
    Engine = "KoKoro", 
    Voice = "af_heart:90,am_adam:10", 
    Port = 8013 
};

// Make the request
var client = new HttpClient();
var requestBody = new
{
    model = "hexgrad/Kokoro-82M",
    input = "Hello from C#!",
    voice = blendedVoice.Voice,
    response_format = "mp3"
};

var json = JsonSerializer.Serialize(requestBody);
var content = new StringContent(json, Encoding.UTF8, "application/json");
var response = await client.PostAsync(
    $"http://localhost:{blendedVoice.Port}/v1/audio/speech", 
    content
);
```
