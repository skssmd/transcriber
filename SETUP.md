# Transcriber Setup Guide

## New Features Added ✨

### 1. **Progress Tracking**
- Real-time progress bar during transcription
- Step-by-step status updates (Converting → Loading Model → Transcribing → Saving → Generating Summary)
- Automatic redirect when complete

### 2. **AI-Powered Summarization**
- Automatic summary generation using Google Gemini API
- Structured output with:
  - **Sections** with timestamps and key notes
  - **Overall Summary**
  - **Conclusion**
  - **Action Items**
- Export summary as JSON

### 3. **Enhanced Export Options**
- Export TXT with timestamps
- Export TXT raw (no timestamps, continuous text)
- Export Word document
- Export AI summary as JSON

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Gemini API Key

To enable AI summarization, you need a Google Gemini API key:

1. Get your API key from: https://makersuite.google.com/app/apikey
2. Set it as an environment variable:

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set GEMINI_API_KEY=your-api-key-here
```

**Linux/Mac:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Or create a `.env` file:**
```
GEMINI_API_KEY=your-api-key-here
```

### 3. Run the Application

```bash
python app.py
```

Visit: http://localhost:5000

---

## How It Works

### Transcription Flow

1. **Upload Audio** → Select file and model settings
2. **Processing Page** → Shows real-time progress with status updates
3. **Transcription** → Whisper AI transcribes with word-level timestamps
4. **AI Summary** → Gemini analyzes transcript and generates structured summary
5. **Session View** → View transcript, highlights, and AI summary

### Progress Stages

- **0-10%**: Starting and converting audio format
- **10-20%**: Loading Whisper AI model
- **20-70%**: Transcribing audio (updates per segment)
- **70-80%**: Saving transcript to file
- **80-100%**: Generating AI summary with Gemini

### AI Summary Structure

The Gemini API analyzes the transcript and provides:

```json
{
  "sections": [
    {
      "section_name": "Introduction",
      "start_time": 0.0,
      "end_time": 120.5,
      "notes": [
        "Speaker introduces topic",
        "Outlines main discussion points"
      ]
    }
  ],
  "summary": "Overall summary of the entire transcript",
  "conclusion": "Main conclusions and takeaways",
  "action_items": [
    "Follow up on X",
    "Schedule meeting about Y"
  ]
}
```

---

## API Endpoints

### New Endpoints

- `GET /api/progress/<session_id>` - Get transcription progress
  ```json
  {
    "status": "transcribing",
    "progress": 45
  }
  ```

- `GET /api/summary/<session_id>` - Get AI-generated summary
  ```json
  {
    "sections": [...],
    "summary": "...",
    "conclusion": "...",
    "action_items": [...]
  }
  ```

### Existing Endpoints

- `POST /` - Upload audio and start transcription
- `GET /session/<session_id>` - View transcription session
- `GET /api/sessions` - List all sessions
- `GET /uploads/<filename>` - Get uploaded audio file

---

## File Structure

```
transcriber/
├── app.py                      # Main Flask application (updated)
├── requirements.txt            # Python dependencies (updated)
├── templates/
│   ├── index.html             # Upload page
│   ├── processing.html        # NEW: Progress tracking page
│   └── session.html           # Session view (updated with AI summary)
├── uploads/                   # Uploaded audio files
├── sessions/                  # Transcription JSON files
└── summaries/                 # NEW: AI-generated summaries
```

---

## Usage Examples

### 1. Basic Transcription

1. Upload audio file
2. Select model (base/small/medium/large)
3. Watch progress in real-time
4. View transcript when complete

### 2. View AI Summary

1. In session view, click "AI Summary" button
2. View structured sections with timestamps
3. Read overall summary and conclusion
4. Check action items
5. Export as JSON if needed

### 3. Export Options

- **Export TXT (Timestamps)**: Clean format with time markers
- **Export TXT (Raw)**: Continuous text for AI processing
- **Export Word**: Document format with timestamps
- **Export Summary**: JSON file with AI analysis

---

## Configuration

### Model Options

- `base`: Fastest, less accurate
- `small`: Good balance
- `medium`: More accurate, slower
- `large`: Most accurate, slowest

### Device Options

- `cpu`: Works everywhere
- `cuda`: NVIDIA GPU (requires CUDA)

### Compute Type

- `int8`: Faster, less memory
- `float16`: Better quality (GPU only)
- `float32`: Best quality, most memory

---

## Troubleshooting

### AI Summary Not Generating

**Issue**: Summary shows "No AI summary available"

**Solutions**:
1. Check if `GEMINI_API_KEY` is set correctly
2. Verify API key is valid at https://makersuite.google.com
3. Check console for error messages
4. Ensure internet connection is active

### Progress Stuck

**Issue**: Progress bar stops updating

**Solutions**:
1. Check browser console for errors
2. Refresh the page
3. Check if Flask server is still running
4. Verify audio file format is supported

### Transcription Fails

**Issue**: Error during transcription

**Solutions**:
1. Ensure ffmpeg is installed
2. Check audio file is not corrupted
3. Try a smaller model size
4. Check available disk space

---

## Notes

- **Progress tracking** works via polling (checks every 1 second)
- **AI summary** generation happens automatically after transcription
- **Summaries** are cached in `summaries/` folder
- **Linter warnings** in `session.html` line 146 are expected (Jinja2 template syntax)

---

## Future Enhancements

Potential features to add:
- Speaker diarization (identify different speakers)
- Real-time transcription streaming
- Multiple language support
- Custom summary templates
- Export to PDF format
- Integration with other AI models (Claude, GPT-4)

---

## Credits

- **Whisper AI**: OpenAI's speech recognition model
- **Faster Whisper**: Optimized implementation by Guillaume Klein
- **Google Gemini**: AI summarization
- **Flask**: Web framework
- **TailwindCSS**: UI styling
