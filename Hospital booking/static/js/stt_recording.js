// static/js/stt_recording.js

let mediaRecorder = null;
let audioChunks = [];

// Convert recorded WEBM → 16-bit WAV (16 kHz mono)
async function convertWebmToWav(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new AudioContext({ sampleRate: 16000 });
    const decoded = await audioCtx.decodeAudioData(arrayBuffer);

    const channelData = decoded.getChannelData(0); // mono
    const wavBuffer = encodeWAV(channelData, 16000);

    return new Blob([wavBuffer], { type: "audio/wav" });
}

function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (offset, string) => {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    };

    // RIFF header
    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);          // PCM chunk size
    view.setUint16(20, 1, true);           // PCM format
    view.setUint16(22, 1, true);           // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true);           // block align
    view.setUint16(34, 16, true);          // bits per sample
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);

    // PCM samples
    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        offset += 2;
    }

    return buffer;
}

// endpoint example: "/api/stt/whisper"
async function startRecording(endpoint) {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
        audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
        try {
            const blob = new Blob(audioChunks, { type: "audio/webm" });

            // Convert to WAV BEFORE sending to backend
            const wavBlob = await convertWebmToWav(blob);

            const formData = new FormData();
            formData.append("audio", wavBlob, "recording.wav");

            const res = await fetch(endpoint, { method: "POST", body: formData });
            const data = await res.json();
            const text = data.text || data.error || "";

            const ev = new CustomEvent("stt-response", { detail: text });
            document.dispatchEvent(ev);
        } catch (err) {
            const ev = new CustomEvent("stt-response", { detail: "Error: " + err });
            document.dispatchEvent(ev);
        }
    };

    mediaRecorder.start();

    // record 5 seconds then stop
    setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
        }
    }, 5000);
}
