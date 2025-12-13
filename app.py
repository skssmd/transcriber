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
    command = [
        "ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1",
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
            generate_summary(session_id, full_text, segment_data)
        
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
            original_path = os.path.join(UPLOAD_FOLDER, filename)
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

def regenerate_summary_task(session_id, session_data, meeting_type_override):
    """Background task to regenerate summary"""
    try:
        progress_key = f"minutes_{session_id}"
        
        processing_status[progress_key] = {
            "status": "detecting_type",
            "progress": 10,
            "step": "Detecting meeting type..."
        }
        
        segments = session_data.get("segments", [])
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
            "status": "mapping_contexts",
            "progress": 20,
            "step": f"Mapping contexts ({meeting_type})..."
        }
        
        # Generate summary with smart chunking
        model = get_model()
        
        # Check if we can reuse cached contexts (only if meeting type matches)
        if os.path.exists(contexts_cache_file):
            with open(contexts_cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                cached_meeting_type = cached_data.get('meeting_type')
                
                # Reuse cache only if meeting type matches or was auto-detected
                if meeting_type_override == "auto" or cached_meeting_type == meeting_type:
                    contexts = cached_data.get('contexts', [])
                    print(f"  ✅ Reusing cached context mapping ({len(contexts)} contexts)")
                else:
                    # Meeting type changed, regenerate contexts
                    print(f"  🔄 Meeting type changed ({cached_meeting_type} → {meeting_type}), regenerating contexts...")
                    contexts = map_contexts(segments, model)
                    # Update cache with new meeting type
                    with open(contexts_cache_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'meeting_type': meeting_type,
                            'contexts': contexts,
                            'generated_at': datetime.now().isoformat()
                        }, f, indent=2)
        else:
            # No cache, map contexts
            contexts = map_contexts(segments, model)
            # Save to cache
            print("  💾 Saving context mapping to cache...")
            with open(contexts_cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'meeting_type': meeting_type,
                    'contexts': contexts,
                    'generated_at': datetime.now().isoformat()
                }, f, indent=2)
        
        processing_status[progress_key] = {
            "status": "generating_notes",
            "progress": 40,
            "step": f"Generating detailed notes for {len(contexts)} contexts individually..."
        }
        
        # Generate sections individually for maximum detail
        sections = []
        
        for idx, context in enumerate(contexts):
            result = generate_section_summary(context, segments, model, meeting_type)
            
            sections.append({
                "section_name": result['name'],
                "start_time": round(result['from_time'], 2),
                "end_time": round(result['end_time'], 2),
                "notes": result['notes']
            })
            
            # Update progress for each context
            progress = 40 + int(((idx + 1) / len(contexts)) * 40)
            processing_status[progress_key] = {
                "status": "generating_notes",
                "progress": progress,
                "step": f"Processing context {idx + 1}/{len(contexts)}: {context['name']}"
            }
        
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

def map_contexts(segments, model):
    """First pass: Map contexts across the transcript using 10-minute chunks"""
    chunks = chunk_by_time(segments, chunk_duration=600)  # 10 minutes
    contexts = []
    ongoing_context = None
    ongoing_chunk_count = 0  # Track how many chunks the current context has spanned
    last_finished_context = None
    previous_chunk_text = None
    
    print(f"Mapping contexts across {len(chunks)} chunks...")
    
    for i, chunk in enumerate(chunks):
        print(f"  📝 Prompting AI: Mapping contexts for chunk {i+1}/{len(chunks)}...")
        model = get_model()  # Get new model instance for each chunk to rotate keys
        chunk_text = ""
        for seg in chunk['segments']:
            chunk_text += f"[{seg['start']}s - {seg['end']}s] {seg['text']}\n"
        
        # Build context history for better understanding
        context_history = ""
        if last_finished_context:
            context_history += f"\nLast finished context: \"{last_finished_context['name']}\" ({last_finished_context['from_time']}s - {last_finished_context['end_time']}s)"
            if 'summary' in last_finished_context:
                context_history += f"\n  Summary: {last_finished_context['summary']}"
        
        # Check if ongoing context needs to be broken into subcontexts (exceeded 2 chunks)
        force_subcontext = ongoing_context and ongoing_chunk_count >= 2
        
        # Build prompt with ongoing context awareness
        if ongoing_context:
            # Determine if this is a subcontext (check for ":" in name)
            is_subcontext = ":" in ongoing_context['name']
            base_context_name = ongoing_context['name'].split(":")[0].strip() if is_subcontext else ongoing_context['name']
            
            if force_subcontext:
                # Force breaking into subcontexts as this context has exceeded 2 chunks
                prompt = f"""Previous context information:
Ongoing context: "{ongoing_context['name']}" (started at {ongoing_context['from_time']}s, has spanned {ongoing_chunk_count} chunks)
  Summary so far: {ongoing_context.get('summary', 'N/A')}

⚠️ CRITICAL: This context has exceeded the maximum of 2 chunks. You MUST break it into subcontexts NOW.

Current chunk ({chunk['start_time']}s - {chunk['end_time']}s):
{chunk_text}

SUBCONTEXT NAMING RULES (MANDATORY):
- Base topic name: "{base_context_name}"
- Format: "Base Topic: Specific Aspect"
- Keep base name SHORT (2-4 words max)
- Subcontext should be descriptive but concise (2-4 words)
- Examples: 
  * "Product Launch: Marketing Strategy"
  * "Product Launch: Budget Discussion"
  * "Incident Report: Initial Account"
  * "Incident Report: Follow-up Actions"

REQUIRED ACTIONS:
1. End the ongoing context "{ongoing_context['name']}" at the point where the subtopic shifts in this chunk
2. Create a NEW subcontext: "{base_context_name}: [New Specific Aspect]"
3. The end_time of the first context MUST equal the from_time of the second context (no gaps/overlaps)

Return JSON array with EXACTLY 2 contexts:
[
  {{
    "name": "{ongoing_context['name']}",
    "from_time": {ongoing_context['from_time']},
    "end_time": [exact timestamp where this ends],
    "status": "finished",
    "is_continuation": true,
    "summary": "Brief summary of what was covered in THIS portion"
  }},
  {{
    "name": "{base_context_name}: [Concise New Aspect Name]",
    "from_time": [same as end_time above],
    "end_time": {chunk['end_time']},
    "status": "finished" or "ongoing",
    "summary": "Brief summary of the new subcontext"
  }}
]

CRITICAL: Return ONLY valid JSON array, no markdown, no explanation."""
            else:
                # Normal ongoing context handling (not forced subcontext yet)
                prompt = f"""Previous context information:
Ongoing context: "{ongoing_context['name']}" (started at {ongoing_context['from_time']}s)
  Chunks spanned: {ongoing_chunk_count + 1} of MAXIMUM 2
  Summary so far: {ongoing_context.get('summary', 'N/A')}
{context_history}

Current chunk ({chunk['start_time']}s - {chunk['end_time']}s):
{chunk_text}

CONTEXT RULES:
- Maximum 2 chunks per context - if exceeding, break into subcontexts
- Subcontext format: "Base Topic: Specific Aspect" (both parts should be 2-4 words)
- Only mark "ongoing" if discussion truly continues beyond this chunk
- Mark "finished" if topic concludes or shifts significantly

DECISION TREE:
1. Is this a CONTINUATION of "{ongoing_context['name']}"?
   - YES, same topic → Set is_continuation: true
     * Will it continue beyond this chunk? → status: "ongoing"
     * Does it conclude in this chunk? → status: "finished"
   
2. Is this a NEW topic/discussion?
   - YES, different topic → Set is_continuation: false
     * Finish ongoing context at transition point
     * Create new context starting at transition point
     * Will new topic continue? → status: "ongoing" or "finished"

CRITICAL RULES:
- from_time and end_time must be EXACT timestamps from the transcript
- NO gaps between contexts (end_time of one = from_time of next)
- NO overlaps allowed
- If entire chunk is continuation, return ONE context with is_continuation: true

Return JSON array (1-2 contexts):
[
  {{
    "name": "Context name (keep concise: 2-5 words)",
    "from_time": [exact timestamp],
    "end_time": [exact timestamp],
    "status": "finished" or "ongoing",
    "is_continuation": true or false,
    "summary": "1-2 sentences describing what was discussed"
  }}
]

CRITICAL: Return ONLY valid JSON array, no markdown, no explanation."""
        else:
            prompt = f"""Analyze this transcript chunk and identify contexts (distinct topics/discussions).
{context_history}

Current chunk ({chunk['start_time']}s - {chunk['end_time']}s):
{chunk_text}

CONTEXT IDENTIFICATION RULES:
- Context = A distinct topic or discussion thread
- Use CONCISE names (2-5 words): "Budget Review", "Incident Report", "Product Demo"
- Maximum 2 chunks per context - plan names that can be subdivided if needed
- Be conservative: Fewer, well-defined contexts > many small fragments
- If entire chunk is ONE topic → Return ONE context

NAMING GUIDELINES:
- Good: "Technical Implementation", "Client Feedback", "Safety Protocol"
- Bad: "Discussion about the technical implementation details and challenges"
- Avoid: overly specific names that can't accommodate subcontexts later

STATUS DECISION:
- "finished": Topic concludes within this chunk
- "ongoing": Topic clearly continues beyond this chunk

CRITICAL RULES:
- Use EXACT timestamps from transcript (not rounded)
- NO gaps or overlaps between contexts
- Each context MUST have a summary (1-2 sentences)

Return JSON array (typically 1-2 contexts per 10-min chunk):
[
  {{
    "name": "Concise Context Name",
    "from_time": [exact timestamp from transcript],
    "end_time": [exact timestamp from transcript],
    "status": "finished" or "ongoing",
    "summary": "Brief 1-2 sentence summary of what was discussed"
  }}
]

CRITICAL: Return ONLY valid JSON array, no markdown, no explanation."""
        
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean markdown
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            chunk_contexts = json.loads(response_text)
            
            # Validate and process contexts
            for ctx_idx, ctx in enumerate(chunk_contexts):
                # Validate required fields
                if not all(key in ctx for key in ['name', 'from_time', 'end_time', 'status']):
                    print(f"  Warning: Context missing required fields, skipping")
                    continue
                
                # Check if this context ended in previous chunk
                if ctx.get('ended_in_previous') and ongoing_context:
                    ongoing_context['end_time'] = ctx['end_time']
                    if 'summary' in ctx:
                        ongoing_context['summary'] = ctx['summary']
                    contexts.append(ongoing_context)
                    last_finished_context = ongoing_context
                    ongoing_context = None
                    ongoing_chunk_count = 0
                    continue
                
                if ctx.get('is_continuation') and ongoing_context:
                    # Continuation of ongoing context
                    ongoing_context['end_time'] = ctx['end_time']
                    if 'summary' in ctx:
                        ongoing_context['summary'] = ctx['summary']
                    
                    if ctx['status'] == 'finished':
                        contexts.append(ongoing_context)
                        last_finished_context = ongoing_context
                        ongoing_context = None
                        ongoing_chunk_count = 0
                    else:
                        # Still ongoing, increment counter
                        ongoing_chunk_count += 1
                else:
                    # New context - finish any ongoing context first
                    if ongoing_context:
                        # Finish ongoing context at the start of this new context
                        ongoing_context['end_time'] = ctx['from_time']
                        contexts.append(ongoing_context)
                        last_finished_context = ongoing_context
                        ongoing_context = None
                        ongoing_chunk_count = 0
                    
                    if ctx['status'] == 'ongoing':
                        # Start new ongoing context
                        ongoing_context = ctx
                        ongoing_chunk_count = 1
                    else:
                        # Finished context
                        contexts.append(ctx)
                        last_finished_context = ctx
            
            print(f"  Chunk {i+1}/{len(chunks)}: Found {len(chunk_contexts)} context(s)")
            
        except json.JSONDecodeError as e:
            print(f"  Error: Invalid JSON response for chunk {i+1}: {e}")
            print(f"  Response was: {response_text[:200]}...")
            continue
        except Exception as e:
            print(f"  Error processing chunk {i+1}: {e}")
            continue
    
    # Add any remaining ongoing context
    if ongoing_context:
        contexts.append(ongoing_context)
    
    return contexts   
def generate_batch_section_summaries(contexts_batch, segments, model, meeting_type):
    """Generate detailed notes for each context individually (one API call per context for maximum detail)"""
    results = []
    
    for context in contexts_batch:
        try:
            result = generate_section_summary(context, segments, model, meeting_type)
            results.append(result)
        except Exception as e:
            print(f"Error generating summary for {context['name']}: {e}")
            results.append({
                'name': context['name'],
                'from_time': context['from_time'],
                'end_time': context['end_time'],
                'notes': ["Error generating notes for this section"]
            })
    
    return results

def generate_section_summary(context, segments, model, meeting_type):
    """Generate detailed notes for a specific context - same structure for all meeting types"""
    print(f"  📝 Prompting AI: Generating notes for '{context['name']}'...")
    model = get_model()  # Get new model instance to rotate keys
    
    # Get segments for this context
    print(segments)
    context_segments = [
        seg for seg in segments 
        if seg['start'] >= context['from_time'] and seg['end'] <= context['end_time']
    ]
    
    context_text = ""
    for seg in context_segments:
        context_text += f"[{seg['start']}s - {seg['end']}s] {seg['text']}\n"
    
    # Same prompt for all meeting types - just generate meeting minutes notes
    prompt = f"""Analyze this section of a meeting and provide CONCISE notes with only KEY information.

Section: {context['name']}
Time: {context['from_time']}s - {context['end_time']}s

Transcript:
{context_text}

Provide BRIEF, CONCISE notes focusing on:
- Key discussion points (summarize, don't repeat everything)
- Important decisions made
- Critical concerns mentioned
- Action items discussed

IMPORTANT GUIDELINES:
- Keep notes SHORT and to the point
- Only include KEY information, not every detail
- Summarize rather than transcribe
- Provide 3-5 notes per section (maximum 8 if needed)
- Each note should be 1-2 sentences
- Focus on what's important, not everything said

Return JSON:
{{
  "notes": [
    "Brief key point 1",
    "Brief key point 2",
    "Brief key point 3"
  ]
}}

IMPORTANT: Return ONLY valid JSON, no markdown."""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        result = json.loads(response_text)
        
        # Add context metadata to result
        return {
            'name': context['name'],
            'from_time': context['from_time'],
            'end_time': context['end_time'],
            'notes': result.get('notes', [])
        }
    except Exception as e:
        print(f"  Error generating notes for {context['name']}: {e}")
        return {
            'name': context['name'],
            'from_time': context['from_time'],
            'end_time': context['end_time'],
            'notes': ["Error generating notes"]
        }

def generate_summary(session_id, full_text, segments):
    """Generate structured summary using smart chunking and context mapping"""
    try:
        model = get_model()
        
        print(f"Starting smart summarization for session {session_id}...")
        
        # Check if contexts are already cached
        contexts_cache_file = os.path.join(SESSION_FOLDER, f"{session_id}_contexts.json")
        
        if os.path.exists(contexts_cache_file):
            print("  ✅ Loading cached context mapping...")
            with open(contexts_cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                meeting_type = cached_data.get('meeting_type', 'REGULAR_MEETING')
                contexts = cached_data.get('contexts', [])
            print(f"  Loaded {len(contexts)} contexts from cache (meeting type: {meeting_type})")
        else:
            # Step 1: Detect meeting type
            meeting_type = detect_meeting_type(segments)
            print(f"  Detected meeting type: {meeting_type}")
            
            # Step 2: Map contexts across transcript
            contexts = map_contexts(segments, model)
            print(f"  Mapped {len(contexts)} contexts")
            
            # Save contexts to cache
            print("  💾 Saving context mapping to cache...")
            with open(contexts_cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'meeting_type': meeting_type,
                    'contexts': contexts,
                    'generated_at': datetime.now().isoformat()
                }, f, indent=2)
            print("  ✅ Context mapping cached")
        
        # Step 3: Generate detailed notes for each context individually
        sections = []
        
        for idx, context in enumerate(contexts):
            print(f"  Generating notes for context {idx + 1}/{len(contexts)}: {context['name']}")
            
            result = generate_section_summary(context, segments, model, meeting_type)
            
            sections.append({
                "section_name": result['name'],
                "start_time": round(result['from_time'], 2),
                "end_time": round(result['end_time'], 2),
                "notes": result['notes']
            })
        
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
