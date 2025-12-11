import streamlit as st
import streamlit.components.v1 as components

def render_audio_recorder(session_id: str, api_url: str, chunk_duration: int = 30, mode: str = "api"):
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 10px; display: flex; gap: 10px; align-items: center; }}
            button {{ padding: 10px 20px; border-radius: 8px; border: 1px solid #ddd; cursor: pointer; }}
            #btn-start {{ background-color: #ff4b4b; color: white; border: none; }}
            #btn-start:disabled {{ opacity: 0.5; }}
            .recording .dot {{ animation: pulse 1s infinite; background-color: #ff4b4b; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} 100% {{ opacity: 1; }} }}
            .dot {{ height: 8px; width: 8px; background-color: #ccc; border-radius: 50%; display: inline-block; }}
        </style>
    </head>
    <body>
        <button id="btn-start" onclick="startRecording()">▶️ Record</button>
        <button id="btn-stop" onclick="stopRecording()" disabled>⏹️ Stop</button>
        <div id="status-display"><span class="dot"></span> <span id="status-text">Ready</span></div>

        <script>
            let mediaRecorder;
            const sessionId = "{session_id}";
            const apiUrl = "{api_url}";
            const chunkDurationMs = {chunk_duration} * 1000;
            const mode = "{mode}"; 
            let chunkCounter = 0;
            let fileExtension = "webm"; // Default

            // 1. DYNAMIC FORMAT SELECTION
            function getBestMimeType() {{
                const types = [
                    "audio/webm;codecs=opus",
                    "audio/webm",
                    "audio/mp4", // Safari
                    "video/mp4"  // Safari fallback
                ];
                for (const type of types) {{
                    if (MediaRecorder.isTypeSupported(type)) {{
                        // Set extension based on type
                        if (type.includes("mp4")) fileExtension = "mp4";
                        else fileExtension = "webm";
                        return type;
                    }}
                }}
                return ""; // Browser default
            }}

            async function startRecording() {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                    
                    const mimeType = getBestMimeType();
                    const options = mimeType ? {{ mimeType }} : undefined;
                    
                    console.log(`🎙️ Starting recorder with mimeType: ${{mimeType || "default"}}`);
                    
                    mediaRecorder = new MediaRecorder(stream, options);
                    
                    mediaRecorder.ondataavailable = (event) => {{
                        if (event.data.size > 0) processChunk(event.data);
                    }};

                    mediaRecorder.start(chunkDurationMs);

                    document.getElementById("btn-start").disabled = true;
                    document.getElementById("btn-stop").disabled = false;
                    document.getElementById("status-display").classList.add("recording");
                    document.getElementById("status-text").innerText = `Recording (${{fileExtension}})...`;
                }} catch (err) {{
                    console.error(err);
                    document.getElementById("status-text").innerText = "Error: " + err.message;
                }}
            }}

            function stopRecording() {{
                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                    mediaRecorder.stop();
                    mediaRecorder.stream.getTracks().forEach(track => track.stop());
                }}
                document.getElementById("btn-start").disabled = false;
                document.getElementById("btn-stop").disabled = true;
                document.getElementById("status-display").classList.remove("recording");
                document.getElementById("status-text").innerText = "Stopped.";
            }}

            async function processChunk(blob) {{
                chunkCounter++;
                // 2. USE DYNAMIC EXTENSION HERE
                const filename = `session_${{sessionId}}_chunk_${{chunkCounter}}.${{fileExtension}}`;

                if (mode === "local_mock") {{
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.style.display = "none";
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    console.log(`💾 Mock Saved: ${{filename}}`);
                }} else {{
                    const formData = new FormData();
                    formData.append("session_id", sessionId);
                    formData.append("file", blob, filename);
                    formData.append("is_last_chunk", "false");

                    try {{
                        const response = await fetch(`${{apiUrl}}/ingest_chunk`, {{
                            method: "POST",
                            body: formData
                        }});
                        if (response.ok) {{
                            document.getElementById("status-text").innerText = `Uploaded Chunk ${{chunkCounter}}`;
                        }} else {{
                            document.getElementById("status-text").innerText = "Upload Failed";
                        }}
                    }} catch (e) {{
                        document.getElementById("status-text").innerText = "Net Error";
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=80)