import subprocess
import os

# ================= CONFIG ================= #

# Folder that contains llama.cpp executable
LLAMA_DIR = r"C:\Users\saran\Music\llama-bin"

# llama.cpp executable
LLAMA_EXE = os.path.join(LLAMA_DIR, "llama-cli.exe")

# TinyLLaMA model (.gguf)
MODEL_FILE = os.path.join(LLAMA_DIR, "tinyllama.gguf")

# Max tokens for short questions
MAX_TOKENS = 64

# ================= FUNCTION ================= #

def tinyllama_chat(system_prompt, user_prompt):
    """
    Runs TinyLLaMA locally using llama.cpp
    Returns a short, clean assistant reply
    """

    if not os.path.exists(LLAMA_EXE):
        return "Assistant unavailable."

    if not os.path.exists(MODEL_FILE):
        return "AI model not found."

    # Build prompt (VERY IMPORTANT FORMAT)
    prompt = f"""<|system|>
{system_prompt}
<|user|>
{user_prompt}
<|assistant|>
"""

    cmd = [
        LLAMA_EXE,
        "-m", MODEL_FILE,
        "-p", prompt,
        "-n", str(MAX_TOKENS),
        "--temp", "0.2",
        "--top-p", "0.9",
        "--repeat-penalty", "1.1",
        "--no-display-prompt"
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        output = result.stdout.strip()

        # ================= CLEAN OUTPUT ================= #
        lines = output.splitlines()
        clean_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(x in line.lower() for x in [
                "<|", "system", "user", "assistant", "instruction"
            ]):
                continue
            clean_lines.append(line)

        if not clean_lines:
            return "Please answer the question."

        # Only first clean sentence
        reply = clean_lines[0]

        # Safety trims
        reply = reply.replace("[", "").replace("]", "")
        reply = reply.replace(":", "", 1)

        return reply.strip()

    except subprocess.TimeoutExpired:
        return "AI took too long to respond."

    except Exception as e:
        print("TinyLLaMA error:", e)
        return "AI error occurred."
