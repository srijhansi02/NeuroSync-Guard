import numpy as np
import soundfile as sf

def generate_mock_voice(filename, frequency, duration=4, sample_rate=16000):
    print(f"🔊 Generating mathematical voice pattern for {filename}...")
    
    # Create a 4-second timeline of audio dots
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Combine multiple sine waves to simulate structural vocal cords/vocal tract pitch
    vocal_pattern = 0.5 * np.sin(2 * np.pi * frequency * t) + \
                    0.25 * np.sin(2 * np.pi * (frequency * 1.5) * t) + \
                    0.1 * np.sin(2 * np.pi * (frequency * 2.1) * t)
    
    # Make it sound slightly natural by gently fading the edges
    fade_size = int(0.1 * sample_rate)
    window = np.ones_like(vocal_pattern)
    window[:fade_size] = np.linspace(0, 1, fade_size)
    window[-fade_size:] = np.linspace(1, 0, fade_size)
    vocal_pattern *= window
    
    # Save directly into your sandbox folder as a standard WAV file!
    sf.write(filename, vocal_pattern, sample_rate)
    print(f"✅ Created clean test file: {filename}")

if __name__ == "__main__":
    print("🚀 Initializing Local Voice Fingerprint Generator...")
    
    # 1. Base voice pattern at 150 Hz (Acts as the normal human anchor track)
    generate_mock_voice("brother_trusted.wav", frequency=150)
    
    # 2. A completely different vocal print at 280 Hz (Acts as the stranger imposter)
    generate_mock_voice("stranger_human.wav", frequency=280)
    
    # 3. Create a copy named brother_clone.wav so your master logic has all 3 targets
    with open("stranger_human.wav", "rb") as src, open("brother_clone.wav", "wb") as dst:
        dst.write(src.read())
    print("✅ Created simulated clone target file.")
    
    print("\n🎉 Done! All artificial benchmarking assets are locked and loaded.")