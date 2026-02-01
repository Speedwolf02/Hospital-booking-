# whisper_stt_processor.py (FINAL PROJECT VERSION USING REFERENCE CODE)

import os
import subprocess
import time

# === ABSOLUTE PATHS ===
WHISPER_EXE_PATH = r"C:\Users\saran\Music\whisper-bin-x64\Release"
WHISPER_CLI_EXE = os.path.join(WHISPER_EXE_PATH, "whisper-cli.exe")

# Models (full paths)
MODEL_PATH = os.path.join(WHISPER_EXE_PATH, "ggml-base.en.bin")
VAD_MODEL_PATH = os.path.join(WHISPER_EXE_PATH, "ggml-silero-v6.2.0.bin")

# Flask project root
FLASK_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER_RELATIVE = "static\\uploads"


def transcribe_audio_whisper(audio_file_path):
    """
    Uses Whisper CLI (with VAD) to transcribe audio.
    Handles .txt generation, multi-extension audio,
    safe deletion, and retry logic.
    """

    # Check executable
    if not os.path.exists(WHISPER_CLI_EXE):
        return f"ERROR: Whisper executable not found at: {WHISPER_CLI_EXE}", False

    # Get clean base name WITHOUT extension
    base_name = os.path.splitext(os.path.basename(audio_file_path))[0]

    # Output directory
    output_dir_abs = os.path.join(FLASK_ROOT, OUTPUT_FOLDER_RELATIVE)

    # Final output base
    output_base_no_ext = os.path.join(output_dir_abs, base_name)

    # Normalize paths for Windows
    input_path_win = audio_file_path.replace("/", "\\")
    output_base_win = output_base_no_ext.replace("/", "\\")

    # ====== Whisper Command ======
    command_str = (
    f'"{WHISPER_CLI_EXE}" '
    f'-m "{MODEL_PATH}" '
    f'-f "{input_path_win}" '
    f'-l "en" '
    f'-otxt '
    f'-of "{output_base_win}"'
)


    print("\n[DEBUG] Whisper Command:")
    print(command_str)

    # Run whisper
    try:
        subprocess.run(
            command_str,
            shell=True,
            check=True,
            timeout=120,
            capture_output=True
        )

        # ====== FIND OUTPUT FILE ======
        for _ in range(20):
            for file in os.listdir(output_dir_abs):
                # Match: base + anything + .txt
                if file.startswith(base_name) and file.endswith(".txt"):
                    txt_path = os.path.join(output_dir_abs, file)

                    try:
                        with open(txt_path, "r", encoding="utf-8") as f:
                            text = f.read().strip()

                        # Clean file after reading
                        os.remove(txt_path)
                        return text, True

                    except PermissionError:
                        time.sleep(0.2)

            time.sleep(0.2)

        return f"ERROR: Whisper output not found for base name: {base_name}", False

    except subprocess.CalledProcessError as e:
        err_msg = (e.stderr or e.stdout).decode("utf-8", errors="ignore")
        return f"Whisper Execution Failed:\n{err_msg}", False

    except Exception as e:
        return f"General STT Error: {str(e)}", False
