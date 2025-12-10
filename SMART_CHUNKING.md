# Smart Chunking & Context Mapping System

## Overview

The transcriber now uses an intelligent multi-pass summarization system that:
1. **Detects meeting type** (Regular Meeting vs Incident Report)
2. **Maps contexts** across the transcript using 5-minute chunks
3. **Tracks ongoing contexts** to prevent cutting discussions mid-topic
4. **Generates detailed notes** for each context with appropriate tone
5. **Creates structured output** with sections, summary, conclusion, and action items

---

## How It Works

### Phase 1: Meeting Type Detection

```
Input: First 10 segments of transcript
Output: REGULAR_MEETING or INCIDENT_REPORT
```

The AI analyzes the beginning of the transcript to determine the meeting type:

- **REGULAR_MEETING**: Business meetings, discussions, planning sessions, team meetings
- **INCIDENT_REPORT**: Investigation, incident review, disciplinary meeting, accident report, complaint investigation

This determines the tone and focus of the summarization.

---

### Phase 2: Context Mapping (10-Minute Chunks)

```
Input: Full transcript split into 10-minute chunks
Output: List of contexts with timestamps and status
```

#### Process:

1. **Split transcript** into 10-minute (600 second) chunks
2. **For each chunk**, ask AI to identify contexts with these guidelines:
   - **Identify major topic changes** - 10 minutes allows for substantial discussions
   - **Contexts can span multiple chunks** - mark as "ongoing"
   - **Chunks can contain partial contexts** - beginning, middle, or end
   - **Only create new contexts when topics genuinely change**
   - **Be conservative** - fewer well-justified contexts are better

3. **Track ongoing contexts** between chunks:
   ```json
   {
     "name": "Discussion about visitor policy",
     "from_time": 120.5,
     "end_time": 450.2,
     "status": "ongoing"
   }
   ```

4. **Merge contexts** when continuation is detected:
   - If chunk 2 continues the context from chunk 1, merge them
   - Update end_time to span both chunks
   - Mark as finished when context concludes

#### Example Flow:

**Chunk 1 (0-300s):**
```json
[
  {
    "name": "Introduction and audio check",
    "from_time": 0,
    "end_time": 45,
    "status": "finished"
  },
  {
    "name": "Incident timeline - Sunday morning",
    "from_time": 45,
    "end_time": 300,
    "status": "ongoing"
  }
]
```

**Chunk 2 (300-600s):**
```
Context History:
- Last finished: "Introduction and audio check" (0s - 45s)
- Ongoing: "Incident timeline - Sunday morning" (started at 45s)

AI Response:
[
  {
    "name": "Incident timeline - Sunday morning",
    "from_time": 300,
    "end_time": 480,
    "status": "finished",
    "is_continuation": true
  },
  {
    "name": "Policy violations discussion",
    "from_time": 480,
    "end_time": 600,
    "status": "ongoing"
  }
]
```

**Chunk 3 (600-900s):**
```
Context History:
- Last finished: "Incident timeline - Sunday morning" (45s - 480s)
- Ongoing: "Policy violations discussion" (started at 480s)

AI uses this to understand the transition and continuity...
```

**Result after merging:**
```json
{
  "name": "Incident timeline - Sunday morning",
  "from_time": 45,
  "end_time": 480,
  "status": "finished"
}
```

---

### Phase 3: Generate Section Notes (Batch Processing)

For efficiency, contexts are processed in **batches of 5** with a single API call per batch:

**Batch prompt structure:**
```
Generate detailed notes for the following 5 contexts from an INCIDENT REPORT.

CONTEXT 1: "Initial discovery" (0s - 120s)
[Transcript text...]
---

CONTEXT 2: "Timeline of events" (120s - 480s)
[Transcript text...]
---

CONTEXT 3: "Policy violations discussion" (480s - 720s)
[Transcript text...]
---

[... up to 5 contexts per batch]

Return JSON array with notes for each context in order:
[
  {"context_index": 0, "notes": ["Note 1", "Note 2"]},
  {"context_index": 1, "notes": ["Note 1", "Note 2"]},
  ...
]
```

**Benefits:**
- **80% fewer API calls** for section notes (5 contexts per call vs 1)
- Faster processing
- Lower rate limit risk
- Consistent quality across related contexts

**Output:** Array of bullet-point notes for each context

---

### Phase 4: Overall Summary Generation

```
Input: All section notes + meeting type
Output: Summary, conclusion, action items
```

Based on the meeting type, generate:

#### For INCIDENT_REPORT:
- **Summary**: Comprehensive summary of the incident, what happened, and key concerns
- **Conclusion**: Final assessment, policy violations identified, and outcome
- **Action Items**: Corrective actions, training requirements, follow-up items

#### For REGULAR_MEETING:
- **Summary**: Comprehensive summary of the meeting discussions and decisions
- **Conclusion**: Key takeaways and outcomes from the meeting
- **Action Items**: Tasks, assignments, next steps

---

## Output Structure

### Final JSON Format:

```json
{
  "session_id": "abc-123",
  "meeting_type": "INCIDENT_REPORT",
  "generated_at": "2025-12-09T12:00:00",
  "transcript_length": 450,
  "sections": [
    {
      "section_name": "Incident Overview",
      "start_time": 0.0,
      "end_time": 120.5,
      "notes": [
        "Care worker Khalipha allowed unknown visitor Jay into service user Dean's home",
        "Jay came to retrieve phone left from previous night's party",
        "No risk assessment conducted before allowing entry"
      ]
    },
    {
      "section_name": "Timeline of Events - Sunday",
      "start_time": 120.5,
      "end_time": 480.2,
      "notes": [
        "Morning: Dean's card declined, only £11 remaining (expected £1000+)",
        "Afternoon: House found extremely dirty with party evidence",
        "Visitor incident: Jay allowed in after Dean said 'let him in'"
      ]
    }
  ],
  "summary": "Care worker violated safeguarding protocols by allowing unauthorized person into vulnerable adult's home without proper verification or risk assessment...",
  "conclusion": "Multiple policy violations identified including visitor access protocol, incident reporting failure, and GDPR breach. Corrective action plan implemented with training and supervision approach...",
  "action_items": [
    "Complete assigned online training modules",
    "Implement no-door-opening policy at Dean's residence",
    "Conduct risk assessment before all decisions",
    "Report all incidents regardless of perceived severity"
  ]
}
```

---

## Benefits of Smart Chunking

### 1. **Context Preservation**
- Discussions aren't artificially cut at 5-minute marks
- Ongoing topics are tracked and merged across chunks
- Natural conversation flow is maintained
- Chunks can contain partial contexts (start, middle, or end)
- Each chunk receives context history (last finished + ongoing) for better continuity understanding

### 2. **Accurate Timestamps**
- Each section has precise start and end times
- Contexts span their actual duration, not arbitrary chunks
- Easy to locate specific discussions in the audio

### 3. **Better Summarization**
- AI sees complete contexts, not fragments
- More coherent and accurate notes
- Proper understanding of cause and effect
- Conservative approach prevents over-segmentation

### 4. **Scalability**
- Works with transcripts of any length
- 10-minute chunks prevent token limit issues and reduce API calls
- Parallel processing possible (future enhancement)
- Flexible context boundaries adapt to content

### 5. **Appropriate Tone**
- Incident reports get formal, investigative tone
- Regular meetings get collaborative, action-oriented tone
- Notes focus on relevant aspects for each type

### 6. **Intelligent Segmentation**
- Doesn't force contexts where none exist
- One chunk can be entirely one context
- Multiple chunks can form one extended context
- AI justifies each context boundary

---

## Example Console Output

```
Starting smart summarization for session abc-123...
  Detected meeting type: INCIDENT_REPORT
Mapping contexts across 4 chunks...
  Chunk 1/4: Found 3 context(s)
  Chunk 2/4: Found 2 context(s)
  Chunk 3/4: Found 3 context(s)
  Chunk 4/4: Found 2 context(s)
  Mapped 10 contexts
  Generating notes for batch 1/2 (5 contexts)
  Generating notes for batch 2/2 (5 contexts)
  Generating overall summary...
  Summary generation complete!
```

---

## Configuration

### Chunk Duration

Default: **600 seconds (10 minutes)**

To change, modify in `app.py`:
```python
def chunk_by_time(segments, chunk_duration=600):  # Change this value
```

**Recommendations:**
- **5 minutes (300s)**: More detailed context mapping, more API calls (may hit rate limits)
- **10 minutes (600s)**: Balanced - fewer API calls, good context detection (default)
- **15 minutes (900s)**: Fastest, fewer contexts, minimal API calls

### Meeting Type Detection

Uses first **10 segments** to detect type.

To change, modify in `app.py`:
```python
for seg in segments[:10]:  # Change this number
```

---

## API Calls Breakdown

For a 40-minute transcript with ~10 contexts:

1. **Meeting Type Detection**: 1 call
2. **Context Mapping**: 4 calls (40 min ÷ 10 min chunks)
3. **Section Notes (Batched)**: 2 calls (10 contexts ÷ 5 per batch)
4. **Overall Summary**: 1 call

**Total**: ~8 API calls

**Comparison:**
- Without batching: ~16 calls (10 individual context calls)
- With 5-minute chunks + no batching: ~21 calls
- **Current (10-min chunks + batching)**: ~8 calls ✅

This is highly efficient because:
- 10-minute chunks reduce context mapping calls by 50%
- Batch processing reduces section notes calls by 80%
- **Total reduction: ~62% fewer API calls**
- Contexts are properly preserved
- No redundant processing
- Minimal rate limit risk

---

## Error Handling

### Context Mapping Errors
- If a chunk fails, it's skipped and next chunk continues
- Ongoing context is preserved even if one chunk fails
- Partial results are still useful

### Section Note Errors
- If notes generation fails, placeholder notes are added
- Error is logged but doesn't stop other sections
- Summary still generated with available data

### Overall Summary Errors
- Full error details saved to summary file
- User sees error message in UI
- Can retry by regenerating summary

---

## Future Enhancements

### Potential Improvements:

1. **Parallel Processing**
   - Process multiple chunks simultaneously
   - Faster for long transcripts
   - Requires careful context merging

2. **Speaker Diarization Integration**
   - Track who said what
   - Context mapping per speaker
   - Better incident reports with speaker attribution

3. **Custom Chunk Strategies**
   - Semantic chunking (break at topic changes)
   - Variable chunk sizes based on content
   - Adaptive chunking for different meeting types

4. **Context Confidence Scores**
   - AI provides confidence for ongoing/finished status
   - Merge decisions based on confidence
   - Better handling of ambiguous transitions

5. **Multi-Language Support**
   - Detect language per chunk
   - Appropriate prompts per language
   - Mixed-language meeting support

---

## Troubleshooting

### Contexts Not Merging Properly

**Issue**: Ongoing contexts create separate sections instead of merging

**Solution**:
- Check if `is_continuation` is being set correctly
- Verify context names match between chunks
- Increase chunk overlap if needed

### Wrong Meeting Type Detected

**Issue**: Regular meeting detected as incident report (or vice versa)

**Solution**:
- Increase number of segments used for detection (currently 10)
- Add more specific keywords to detection prompt
- Manually specify meeting type (future feature)

### Too Many/Few Contexts

**Issue**: Context mapping creates too granular or too broad sections

**Solution**:
- Adjust chunk duration (smaller = more granular)
- Modify context detection prompt
- Add minimum context duration threshold

---

## Best Practices

1. **Audio Quality**: Better audio = better transcription = better context mapping
2. **Clear Discussions**: Well-structured meetings produce better summaries
3. **API Key**: Ensure Gemini API key has sufficient quota
4. **Review Output**: Always review AI-generated summaries for accuracy
5. **Feedback Loop**: Note patterns in errors to improve prompts

---

## Credits

- **Smart Chunking Algorithm**: Custom implementation
- **Context Mapping**: Inspired by conversation threading techniques
- **Google Gemini**: AI model for analysis
- **Faster Whisper**: Transcription engine
