from flask import Flask, render_template, request, send_from_directory, jsonify, redirect, url_for
from faster_whisper import WhisperModel
import os
import uuid
import json
import tempfile
import shutil
import subprocess
import threading
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
SESSION_FOLDER = "sessions"
SUMMARY_FOLDER = "summaries"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SESSION_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

# Configure Gemini API (supports multiple API keys for load distribution)
# Try to import from settings.py first, fallback to environment variables
try:
    from settings import GEMINI_API_KEYS
    print(f"Loaded {len(GEMINI_API_KEYS)} API key(s) from settings.py")
except ImportError:
    # Fallback to environment variables
    GEMINI_API_KEYS_STR = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS_STR.split(",") if key.strip()]
    if GEMINI_API_KEYS:
        print(f"Loaded {len(GEMINI_API_KEYS)} API key(s) from environment variables")
    else:
        print("WARNING: No API keys found. Please create settings.py or set GEMINI_API_KEYS environment variable")

current_api_key_index = 0

def get_next_api_key():
    """Rotate through available API keys for load distribution"""
    global current_api_key_index
    if not GEMINI_API_KEYS:
        return None
    key = GEMINI_API_KEYS[current_api_key_index]
    current_api_key_index = (current_api_key_index + 1) % len(GEMINI_API_KEYS)
    return key

def get_model():
    """Get a Gemini model instance with the next available API key"""
    api_key = get_next_api_key()
    if api_key:
        # Show which key is being used (masked for security)
        key_preview = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "***"
        print(f"  🔑 Using API key: {key_preview}")
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    return None

# Initialize with first key
if GEMINI_API_KEYS:
    genai.configure(api_key=GEMINI_API_KEYS[0])

# Global dict to track processing progress
processing_status = {}
def convert_to_wav(input_path, output_path):
    """Convert any audio format to 16kHz mono WAV using ffmpeg."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise FileNotFoundError(
            "ffmpeg not found. Please install ffmpeg and make sure it is in your system PATH. "
            "Download from: https://ffmpeg.org/download.html"
        )
    command = [
        ffmpeg_path, "-i", input_path, "-ar", "16000", "-ac", "1",
        "-y", output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def process_transcription(session_id, audio_path, filename, model_size, device, compute_type):
    """Background task to process transcription with progress updates"""
    try:
        processing_status[session_id] = {"status": "converting", "progress": 10}
        
        # Convert to WAV
        wav_path = os.path.join(tempfile.gettempdir(), f"{session_id}.wav")
        convert_to_wav(audio_path, wav_path)
        
        processing_status[session_id] = {"status": "loading_model", "progress": 20}
        
        # Load model
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        
        processing_status[session_id] = {"status": "transcribing", "progress": 30}
        
        # Transcribe
        segments, info = model.transcribe(wav_path, word_timestamps=True)
        
        # Build segment data
        segment_data = []
        full_text = ""
        segment_list = list(segments)
        total_segments = len(segment_list)
        
        for i, segment in enumerate(segment_list):
            text = segment.text.strip()
            full_text += text + " "
            segment_data.append({
                "id": i,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": text,
                "words": [
                    {
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "word": w.word.strip()
                    } for w in segment.words or []
                ]
            })
            # Update progress
            progress = 30 + int((i / total_segments) * 40)
            processing_status[session_id] = {"status": "transcribing", "progress": progress}
        
        processing_status[session_id] = {"status": "saving", "progress": 75}
        
        result = {
            "session_id": session_id,
            "name": filename,
            "audio_url": f"/uploads/{filename}",
            "text": full_text.strip(),
            "segments": segment_data
        }
        
        # Save session file
        with open(os.path.join(SESSION_FOLDER, f"{session_id}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        processing_status[session_id] = {"status": "generating_summary", "progress": 80}
        
        # Generate summary with Gemini if API keys are available
        if GEMINI_API_KEYS:
            # Strip word-level data to save tokens and avoid massive payloads
            stripped_segments = strip_words_from_segments(segment_data)
            generate_summary(session_id, full_text, stripped_segments)
        
        processing_status[session_id] = {"status": "complete", "progress": 100}
        
        # Cleanup
        if os.path.exists(wav_path):
            os.remove(wav_path)
            
    except Exception as e:
        processing_status[session_id] = {"status": "error", "progress": 0, "error": str(e)}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        audio = request.files.get("audio")
        model_size = "tiny"
        device = request.form.get("device", "cpu")
        compute_type = request.form.get("compute_type", "int8")

        if audio:
            # Generate session ID and save file
            session_id = str(uuid.uuid4())
            filename = audio.filename
            original_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
            audio.save(original_path)
            
            # Initialize status
            processing_status[session_id] = {"status": "starting", "progress": 0}
            
            # Start background processing
            thread = threading.Thread(
                target=process_transcription,
                args=(session_id, original_path, filename, model_size, device, compute_type)
            )
            thread.daemon = True
            thread.start()
            
            # Return processing page
            return render_template("processing.html", session_id=session_id)

    return render_template("index.html")

@app.route("/session/<session_id>")
def session_view(session_id):
    try:
        with open(os.path.join(SESSION_FOLDER, f"{session_id}.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return render_template("session.html", data=data)
    except FileNotFoundError:
        return "Session not found", 404

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = []
    for filename in os.listdir(SESSION_FOLDER):
        if filename.endswith(".json"):
            session_id = filename.replace(".json", "")
            with open(os.path.join(SESSION_FOLDER, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions.append({
                    "session_id": session_id,
                    "name": data.get("name", "Untitled")
                })
    return jsonify(sessions)

@app.route("/api/progress/<session_id>")
def get_progress(session_id):
    """Get processing progress for a session"""
    status = processing_status.get(session_id, {"status": "unknown", "progress": 0})
    return jsonify(status)

@app.route("/api/summary/<session_id>")
def get_summary(session_id):
    """Get generated summary for a session"""
    summary_path = os.path.join(SUMMARY_FOLDER, f"{session_id}_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Summary not found"}), 404

@app.route("/api/regenerate-summary/<session_id>", methods=["POST"])
def regenerate_summary(session_id):
    """Regenerate summary with specified meeting type"""
    try:
        data = request.json
        meeting_type_override = data.get("meeting_type", "auto")
        
        # Load session data
        session_path = os.path.join(SESSION_FOLDER, f"{session_id}.json")
        if not os.path.exists(session_path):
            return jsonify({"error": "Session not found"}), 404
        
        with open(session_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        
        # Initialize progress
        processing_status[f"minutes_{session_id}"] = {
            "status": "starting",
            "progress": 0,
            "step": "Initializing..."
        }
        
        # Start background task
        thread = threading.Thread(
            target=regenerate_summary_task,
            args=(session_id, session_data, meeting_type_override)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/minutes-progress/<session_id>")
def get_minutes_progress(session_id):
    """Get progress of minutes generation"""
    status = processing_status.get(f"minutes_{session_id}", {
        "status": "unknown",
        "progress": 0,
        "step": "Unknown"
    })
    return jsonify(status)

def find_failed_sections(summary_data):
    """Find sections with error notes"""
    failed = []
    for idx, section in enumerate(summary_data.get("sections", [])):
        notes = section.get("notes", [])
        if notes == ["Error generating notes"] or "Error generating notes" in notes:
            failed.append({
                "index": idx,
                "section_name": section.get("section_name"),
                "start_time": section.get("start_time"),
                "end_time": section.get("end_time")
            })
    return failed

@app.route("/api/retry-failed-sections/<session_id>", methods=["POST"])
def retry_failed_sections(session_id):
    """Retry generating notes for sections that failed"""
    try:
        # Load summary
        summary_path = os.path.join(SUMMARY_FOLDER, f"{session_id}_summary.json")
        if not os.path.exists(summary_path):
            return jsonify({"error": "Summary not found"}), 404
        
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
        
        # Find failed sections
        failed = find_failed_sections(summary_data)
        if not failed:
            return jsonify({"message": "No failed sections found", "retried": 0})
        
        # Load contexts
        contexts_path = os.path.join(SESSION_FOLDER, f"{session_id}_contexts.json")
        if not os.path.exists(contexts_path):
            return jsonify({"error": "Contexts not found"}), 404
        
        with open(contexts_path, "r", encoding="utf-8") as f:
            contexts_data = json.load(f)
            contexts = contexts_data.get("contexts", [])
            meeting_type = contexts_data.get("meeting_type", "REGULAR_MEETING")
        
        # Load session segments
        session_path = os.path.join(SESSION_FOLDER, f"{session_id}.json")
        if not os.path.exists(session_path):
            return jsonify({"error": "Session not found"}), 404
        
        with open(session_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
            segments = strip_words_from_segments(session_data.get("segments", []))
        
        # Retry each failed section
        retried_count = 0
        for failed_section in failed:
            section_idx = failed_section["index"]
            section = summary_data["sections"][section_idx]
            
            # Find matching context
            matching_context = None
            for ctx in contexts:
                if (abs(ctx.get("from_time", 0) - section["start_time"]) < 1.0 and 
                    abs(ctx.get("end_time", 0) - section["end_time"]) < 1.0):
                    matching_context = ctx
                    break
            
            if not matching_context:
                print(f"  ⚠️ No matching context found for section '{section['section_name']}'")
                continue
            
            # Retry generation
            print(f"  🔄 Retrying section '{section['section_name']}' ({section['start_time']}s - {section['end_time']}s)...")
            model = get_model()
            result = generate_section_summary(matching_context, segments, model, meeting_type)
            
            # Update section with new notes
            summary_data["sections"][section_idx]["notes"] = result.get("notes", ["Error generating notes"])
            retried_count += 1
        
        # Save updated summary
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)
        
        return jsonify({
            "success": True,
            "retried": retried_count,
            "total_failed": len(failed)
        })
        
    except Exception as e:
        print(f"Error retrying failed sections: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def regenerate_summary_task(session_id, session_data, meeting_type_override):
    """Background task to regenerate summary"""
    try:
        progress_key = f"minutes_{session_id}"
        
        processing_status[progress_key] = {
            "status": "detecting_type",
            "progress": 10,
            "step": "Detecting meeting type..."
        }
        
        segments = strip_words_from_segments(session_data.get("segments", []))
        full_text = session_data.get("text", "")
        
        # Check if contexts are already cached
        contexts_cache_file = os.path.join(SESSION_FOLDER, f"{session_id}_contexts.json")
        
        # Use override or detect meeting type
        if meeting_type_override == "auto":
            # Check cache first
            if os.path.exists(contexts_cache_file):
                with open(contexts_cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    meeting_type = cached_data.get('meeting_type', 'REGULAR_MEETING')
            else:
                meeting_type = detect_meeting_type(segments)
        else:
            meeting_type = meeting_type_override
        
        processing_status[progress_key] = {
            "status": "processing_stream",
            "progress": 20,
            "step": f"Processing transcript stream ({meeting_type})..."
        }
        
        # Generate summary with smart chunking (stream processing)
        model = get_model()
        
        sections = process_chunk_stream(segments, model, meeting_type)
        
        processing_status[progress_key] = {
            "status": "finalizing",
            "progress": 85,
            "step": "Generating summary and conclusion..."
        }
        
        print("  📝 Prompting AI: Generating final summary and conclusion...")
        model = get_model()  # Get new model instance to rotate keys
        
        # Generate overall summary
        sections_summary = ""
        for sec in sections:
            sections_summary += f"\n{sec['section_name']} ({sec['start_time']}s - {sec['end_time']}s):\n"
            for note in sec['notes']:
                sections_summary += f"  - {note}\n"
        
        # Generate summary, conclusion, and action items (for all meeting types)
        final_prompt = f"""Based on this meeting analysis, provide:

Sections discussed:
{sections_summary}

Return JSON:
{{
  "summary": "Comprehensive summary of the meeting discussions and decisions",
  "conclusion": "Key takeaways and outcomes from the meeting",
  "action_items": [
    {{
      "action_for": "Person/Team responsible",
      "action_items": [
        "Specific action 1",
        "Specific action 2"
      ]
    }},
    {{
      "action_for": "Another person/team",
      "action_items": [
        "Specific action 1"
      ]
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON, no markdown."""
        
        response = model.generate_content(final_prompt)
        response_text = response.text.strip()
        
        # Clean markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        final_data = json.loads(response_text)
        
        # Save summary
        summary_data = {
            "session_id": session_id,
            "meeting_type": meeting_type,
            "generated_at": datetime.now().isoformat(),
            "transcript_length": len(segments),
            "sections": sections,
            "summary": final_data.get("summary", ""),
            "conclusion": final_data.get("conclusion", ""),
            "action_items": final_data.get("action_items", [])
        }
        
        # For incident reports, generate additional incident_report section
        if meeting_type == "INCIDENT_REPORT":
            print("  📝 Prompting AI: Generating incident report section...")
            model = get_model()  # Get new model instance to rotate keys
            
            incident_prompt = f"""You are generating the INCIDENT REPORT section of a formal investigation report.

Based on these meeting minutes:
{sections_summary}

CRITICAL INSTRUCTIONS:
1. **EXTRACT ALL NAMES**: Identify every person mentioned in the INCIDENT (not meeting attendees)
2. **CONCISE TIMELINE**: List key events chronologically - be brief and factual
3. **KEY FACTS ONLY**: Include only the most important facts (3-5 facts, max 8)
4. **USE MARKDOWN**: Use markdown formatting (bold, italic, lists) for better organization
5. **FORMAL TONE**: Write like an official investigation report

Return JSON with this EXACT structure:
{{
  "background": "Brief 2-3 sentence background. Use **bold** for key terms and names.",
  "key_facts": [
    "**Key fact 1**: Description (1-2 sentences). Use **bold** for important terms.",
    "**Key fact 2**: Description (1-2 sentences)",
    "**Key fact 3**: Description (1-2 sentences)"
  ],
  "timeline": [
    {{
      "time_period": "**Morning Visit** (9:00 AM - 12:00 PM)",
      "events": [
        "**Event 1**: What happened (1-2 sentences). Use **bold** for names and key actions.",
        "**Event 2**: What happened (1-2 sentences)",
        "**Event 3**: What happened (1-2 sentences)"
      ]
    }}
  ],
  "concerns_identified": [
    {{"category": "Policy Violations", "details": ["**Violation 1**: Brief description", "**Violation 2**: Brief description"]}},
    {{"category": "Risk Assessment Failures", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Documentation Failures", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Professional Boundaries", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Other Concerns", "details": ["**Concern 1**: Brief description"]}}
  ],
  "evidence_collected": [
    "**Evidence 1**: Brief description",
    "**Evidence 2**: Brief description",
    "**Evidence 3**: Brief description"
  ],
  "parties_involved": [
    {{"name": "**Person's Full Name** (Role)", "involvement": "Brief 1-2 sentence description. Use **bold** for key actions."}}
  ]
}}

IMPORTANT: 
- Return ONLY valid JSON (strings can contain markdown)
- Use markdown formatting: **bold** for emphasis, *italic* for notes
- Keep everything CONCISE and to the point
- Extract names of people involved in the INCIDENT, not meeting participants
- Provide 3-5 items per section (maximum 8 if needed)
- Each item should be 1-2 sentences
- Focus on KEY information only"""
            
            response = model.generate_content(incident_prompt)
            response_text = response.text.strip()
            
            # Clean markdown
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            incident_report_data = json.loads(response_text)
            summary_data["incident_report"] = incident_report_data
        
        summary_path = os.path.join(SUMMARY_FOLDER, f"{session_id}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)
        
        processing_status[progress_key] = {
            "status": "complete",
            "progress": 100,
            "step": "Complete!"
        }
        
    except Exception as e:
        print(f"Error regenerating summary: {e}")
        import traceback
        traceback.print_exc()
        processing_status[f"minutes_{session_id}"] = {
            "status": "error",
            "progress": 0,
            "step": "Error occurred",
            "error": str(e)
        }

def detect_meeting_type(segments):
    """Detect if this is a regular meeting or incident report"""
    print("  📝 Prompting AI: Detecting meeting type...")
    model = get_model()
    
    # Use first 10 segments to detect type
    sample_text = ""
    for seg in segments[:10]:
        sample_text += f"{seg['text']} "
    
    prompt = f"""Analyze this transcript excerpt and determine if it's a REGULAR_MEETING or INCIDENT_REPORT.

Transcript excerpt:
{sample_text}

Respond with ONLY one word: REGULAR_MEETING or INCIDENT_REPORT

REGULAR_MEETING: Normal business meetings, discussions, planning sessions, team meetings
INCIDENT_REPORT: Investigation, incident review, disciplinary meeting, accident report, complaint investigation"""
    
    try:
        response = model.generate_content(prompt)
        meeting_type = response.text.strip().upper()
        if "INCIDENT" in meeting_type:
            return "INCIDENT_REPORT"
        return "REGULAR_MEETING"
    except:
        return "REGULAR_MEETING"  # Default

def chunk_by_time(segments, chunk_duration=300):
    """Split segments into time-based chunks (default 5 minutes = 300 seconds)"""
    chunks = []
    current_chunk = []
    chunk_start = 0
    
    for seg in segments:
        if not current_chunk:
            chunk_start = seg['start']
        
        current_chunk.append(seg)
        
        # Check if we've exceeded chunk duration
        if seg['end'] - chunk_start >= chunk_duration:
            chunks.append({
                'segments': current_chunk,
                'start_time': chunk_start,
                'end_time': seg['end']
            })
            current_chunk = []
    
    # Add remaining segments
    if current_chunk:
        chunks.append({
            'segments': current_chunk,
            'start_time': chunk_start,
            'end_time': current_chunk[-1]['end']
        })
    
    return chunks

def strip_words_from_segments(segments):
    """Remove word-level timestamps to reduce token usage and JSON size in prompts"""
    stripped = []
    for seg in segments:
        stripped.append({
            'id': seg.get('id'),
            'start': seg.get('start'),
            'end': seg.get('end'),
            'text': seg.get('text', '')
        })
    return stripped

def get_segments_text(segments, target_duration=45):
    """Group segments into larger blocks of text with timestamps to reduce token overhead"""
    if not segments:
        return ""
    
    output_text = ""
    current_group = []
    group_start = None
    
    for seg in segments:
        if group_start is None:
            group_start = seg['start']
        
        current_group.append(seg['text'])
        
        # If we reached the target duration or it's the last segment
        if seg['end'] - group_start >= target_duration:
            text_block = " ".join(current_group)
            output_text += f"[{round(group_start, 2)}s - {round(seg['end'], 2)}s] {text_block}\n"
            current_group = []
            group_start = None
            
    if current_group:
        output_text += f"[{round(group_start, 2)}s - {round(segments[-1]['end'], 2)}s] {' '.join(current_group)}\n"
        
    return output_text

def process_chunk_stream(segments, model, meeting_type="REGULAR_MEETING"):
    """
    Single-pass processing: Process segments in chunks, identifying contexts
    and generating/updating notes in real-time.
    """
    # 1. Chunk by time (15-20 min chunks for better context)
    chunk_duration = 1000  # ~16 minutes
    chunks = chunk_by_time(segments, chunk_duration=chunk_duration)
    
    print(f"Processing transcript in {len(chunks)} stream chunks...")
    
    final_sections = []
    ongoing_context = None
    
    for i, chunk in enumerate(chunks):
        chunk_start = round(chunk['start_time'], 2)
        chunk_end = round(chunk['end_time'], 2)
        print(f"  🌊 Stream Processing Chunk {i+1}/{len(chunks)} ({chunk_start}s - {chunk_end}s)...")
        
        model = get_model() # Rotate keys
        
        # Get text for this chunk
        chunk_text = get_segments_text(chunk['segments'], target_duration=60)
        
        # Prepare ongoing context info
        ongoing_context_prompt = ""
        if ongoing_context:
            ongoing_context_prompt = f"""
ONGOING CONTEXT FROM PREVIOUS CHUNK:
Name: "{ongoing_context['name']}"
Started at: {ongoing_context['from_time']}s
Summary/Notes so far:
{json.dumps(ongoing_context['notes'][-3:], indent=2)} (last 3 points)

INSTRUCTION FOR ONGOING CONTEXT:
1. This context continues into the current chunk.
2. **GENERATE NEW NOTES ONLY**: meaningful updates from THIS CHUNK.
3. **DO NOT REPEAT** information from the previous chunk.
4. If the topic finishes in this chunk, mark as "finished".
5. If it continues to the NEXT chunk, mark as "ongoing".
"""

        prompt = f"""Analyze this meeting transcript chunk. Identify topics (contexts) and generate detailed notes.

TRANSCRIPT CHUNK ({chunk_start}s - {chunk_end}s):
{chunk_text}
{ongoing_context_prompt}

INSTRUCTIONS:
1. **Identify Contexts**: logical sections/topics in the meeting.
2. **Generate Notes**: detailed, concise notes for each context.
3. **Handle Transitions**: When a topic changes, end the current context and start a new one.

OUTPUT RULES:
- **name**: Concise topic name (2-5 words)
- **from_time**: Start time (seconds)
- **end_time**: End time (seconds) - MUST MATCH CHUNK END TIME if "ongoing"
- **status**: "finished" (topic ends here) or "ongoing" (topic continues to next chunk)
- **notes**: List of strings. For ongoing contexts, provide ONLY NEW NOTES from this chunk.

format:
[
  {{
    "name": "Topic Name",
    "from_time": 123.0,
    "end_time": 456.0,
    "status": "finished",
    "notes": ["Point 1", "Point 2"]
  }}
]

CRITICAL:
- Return ONLY valid JSON.
- NO overlapping times (except boundaries).
- Gaps are allowed if no meaningful content exists, but prefer continuous coverage.
"""
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            chunk_results = json.loads(response_text)
            
            # Process results
            for res in chunk_results:
                # Validate
                if 'name' not in res or 'notes' not in res:
                    continue
                
                # Logic for ongoing vs finished
                if res.get('status') == 'ongoing':
                    if ongoing_context and res['name'] == ongoing_context['name']:
                        # Append NEW notes to existing ongoing context
                        ongoing_context['notes'].extend(res['notes'])
                        ongoing_context['end_time'] = res['end_time']
                    else:
                        # New ongoing context detected
                        ongoing_context = res
                else:
                    # Finished context
                    if ongoing_context and res['name'] == ongoing_context['name']:
                        # It was ongoing, now finished. Combine and close.
                        ongoing_context['notes'].extend(res['notes'])
                        ongoing_context['end_time'] = res['end_time']
                        final_sections.append({
                            "section_name": ongoing_context['name'],
                            "start_time": round(float(ongoing_context.get('from_time', chunk_start)), 2),
                            "end_time": round(float(ongoing_context.get('end_time', chunk_end)), 2),
                            "notes": ongoing_context['notes']
                        })
                        ongoing_context = None
                    else:
                        # Just a regular finished context in this chunk
                        final_sections.append({
                            "section_name": res['name'],
                            "start_time": round(float(res.get('from_time', chunk_start)), 2),
                            "end_time": round(float(res.get('end_time', chunk_end)), 2),
                            "notes": res['notes']
                        })
                        ongoing_context = None
            
        except Exception as e:
            print(f"Error processing chunk {i}: {e}")
            continue

    # After all chunks, if there's still an ongoing context, close it
    if ongoing_context:
        final_sections.append({
            "section_name": ongoing_context['name'],
            "start_time": round(float(ongoing_context.get('from_time', 0)), 2),
            "end_time": round(float(ongoing_context.get('end_time', chunks[-1]['end_time'])), 2),
            "notes": ongoing_context['notes']
        })

    return final_sections


def generate_summary(session_id, full_text, segments):
    """Generate structured summary using streamed chunk processing"""
    try:
        model = get_model()
        
        print(f"Starting optimized stream summarization for session {session_id}...")
        
        # Step 1: Detect meeting type
        meeting_type = detect_meeting_type(segments)
        print(f"  Detected meeting type: {meeting_type}")

        # Step 2: Stream Process (Contexts + Notes in one pass)
        sections = process_chunk_stream(segments, model, meeting_type)
        print(f"  Generated {len(sections)} sections via stream processing.")
                
        # Step 4: Generate overall summary, conclusion, and action items
        print("  Generating overall summary...")
        print("  📝 Prompting AI: Generating final summary and conclusion...")
        model = get_model()  # Get new model instance to rotate keys
        
        # Create summary of all sections
        sections_summary = ""
        for sec in sections:
            sections_summary += f"\n{sec['section_name']} ({sec['start_time']}s - {sec['end_time']}s):\n"
            for note in sec['notes']:
                sections_summary += f"  - {note}\n"
        
        # Generate summary, conclusion, and action items (for all meeting types)
        final_prompt = f"""Based on this meeting analysis, provide:

Sections discussed:
{sections_summary}

Return JSON:
{{
  "summary": "Comprehensive summary of the meeting discussions and decisions",
  "conclusion": "Key takeaways and outcomes from the meeting",
  "action_items": [
    {{
      "action_for": "Person/Team responsible",
      "action_items": [
        "Specific action 1",
        "Specific action 2"
      ]
    }},
    {{
      "action_for": "Another person/team",
      "action_items": [
        "Specific action 1"
      ]
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON, no markdown."""
        
        response = model.generate_content(final_prompt)
        response_text = response.text.strip()
        
        # Clean markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        final_data = json.loads(response_text)
        
        # Combine everything
        summary_data = {
            "session_id": session_id,
            "meeting_type": meeting_type,
            "generated_at": datetime.now().isoformat(),
            "transcript_length": len(segments),
            "sections": sections,
            "summary": final_data.get("summary", ""),
            "conclusion": final_data.get("conclusion", ""),
            "action_items": final_data.get("action_items", [])
        }
        
        # For incident reports, generate additional incident_report section
        if meeting_type == "INCIDENT_REPORT":
            print("  📝 Prompting AI: Generating incident report section...")
            model = get_model()  # Get new model instance to rotate keys
            
            incident_prompt = f"""You are generating the INCIDENT REPORT section of a formal investigation report.

Based on these meeting minutes:
{sections_summary}

CRITICAL INSTRUCTIONS:
1. **EXTRACT ALL NAMES**: Identify every person mentioned in the INCIDENT (not meeting attendees)
2. **CONCISE TIMELINE**: List key events chronologically - be brief and factual
3. **KEY FACTS ONLY**: Include only the most important facts (3-5 facts, max 8)
4. **USE MARKDOWN**: Use markdown formatting (bold, italic, lists) for better organization
5. **FORMAL TONE**: Write like an official investigation report

Return JSON with this EXACT structure:
{{
  "background": "Brief 2-3 sentence background. Use **bold** for key terms and names.",
  "key_facts": [
    "**Key fact 1**: Description (1-2 sentences). Use **bold** for important terms.",
    "**Key fact 2**: Description (1-2 sentences)",
    "**Key fact 3**: Description (1-2 sentences)"
  ],
  "timeline": [
    {{
      "time_period": "**Morning Visit** (9:00 AM - 12:00 PM)",
      "events": [
        "**Event 1**: What happened (1-2 sentences). Use **bold** for names and key actions.",
        "**Event 2**: What happened (1-2 sentences)",
        "**Event 3**: What happened (1-2 sentences)"
      ]
    }}
  ],
  "concerns_identified": [
    {{"category": "Policy Violations", "details": ["**Violation 1**: Brief description", "**Violation 2**: Brief description"]}},
    {{"category": "Risk Assessment Failures", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Documentation Failures", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Professional Boundaries", "details": ["**Concern 1**: Brief description"]}},
    {{"category": "Other Concerns", "details": ["**Concern 1**: Brief description"]}}
  ],
  "evidence_collected": [
    "**Evidence 1**: Brief description",
    "**Evidence 2**: Brief description",
    "**Evidence 3**: Brief description"
  ],
  "parties_involved": [
    {{"name": "**Person's Full Name** (Role)", "involvement": "Brief 1-2 sentence description. Use **bold** for key actions."}}
  ]
}}

IMPORTANT: 
- Return ONLY valid JSON (strings can contain markdown)
- Use markdown formatting: **bold** for emphasis, *italic* for notes
- Keep everything CONCISE and to the point
- Extract names of people involved in the INCIDENT, not meeting participants
- Provide 3-5 items per section (maximum 8 if needed)
- Each item should be 1-2 sentences
- Focus on KEY information only"""
            
            response = model.generate_content(incident_prompt)
            response_text = response.text.strip()
            
            # Clean markdown
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            incident_report_data = json.loads(response_text)
            summary_data["incident_report"] = incident_report_data
        
        # Save summary
        summary_path = os.path.join(SUMMARY_FOLDER, f"{session_id}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)
        
        print(f"  Summary generation complete!")
            
    except Exception as e:
        print(f"Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        # Save error info
        error_data = {
            "session_id": session_id,
            "error": str(e),
            "generated_at": datetime.now().isoformat()
        }
        summary_path = os.path.join(SUMMARY_FOLDER, f"{session_id}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(error_data, f, indent=2)

if __name__ == "__main__":
    app.run(debug=True)
