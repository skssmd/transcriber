# Context Caching System

## Overview

The smart context mapping is now **cached** to avoid regenerating contexts every time you generate a summary. This saves API calls, time, and money!

---

## How It Works

### First Time (No Cache)
```
1. Upload audio → Transcribe
2. Generate Minutes:
   - Detect meeting type (1 API call)
   - Map contexts in 10-min chunks (6 API calls for 1-hour meeting)
   - Generate notes per context (8 API calls for 8 contexts)
   - Generate final summary (1 API call)
   
Total: ~16 API calls
Time: ~2-3 minutes
```

### Second Time (With Cache)
```
1. Same session, regenerate with different type:
   - Load cached contexts ✅ (0 API calls)
   - Generate notes per context (8 API calls)
   - Generate final summary (1 API call)
   
Total: ~9 API calls (saved 7 calls!)
Time: ~1-2 minutes (50% faster!)
```

---

## What Gets Cached

**File:** `sessions/{session_id}_contexts.json`

**Contents:**
```json
{
  "meeting_type": "INCIDENT_REPORT",
  "generated_at": "2024-12-09T15:20:30.123456",
  "contexts": [
    {
      "name": "Opening Discussion",
      "from_time": 0,
      "end_time": 245.5,
      "status": "finished",
      "summary": "Brief summary of what was discussed"
    },
    {
      "name": "Financial Concerns",
      "from_time": 245.5,
      "end_time": 520.3,
      "status": "finished",
      "summary": "Discussion about financial issues"
    }
  ]
}
```

---

## When Cache is Used

### ✅ Cache Reused
- **Regenerate with "Auto" type** → Uses cached meeting type and contexts
- **Regenerate with same type** → Uses cached contexts
- **Generate summary again** → Uses cached contexts

### 🔄 Cache Regenerated
- **Meeting type changed** → Regenerates contexts with new type
  - Example: Change from "Regular Meeting" to "Incident Report"
- **First time generating** → No cache exists yet

### 🗑️ Cache Cleared
- **Delete session** → Cache file deleted with session
- **Manual deletion** → Delete `{session_id}_contexts.json` file

---

## Console Output

### First Generation (No Cache)
```
Starting smart summarization for session abc123...
  📝 Prompting AI: Detecting meeting type...
  🔑 Using API key: AIzaSyBRFKZ...YfWU
  Detected meeting type: INCIDENT_REPORT

Mapping contexts across 6 chunks...
  📝 Prompting AI: Mapping contexts for chunk 1/6...
  🔑 Using API key: AIzaSyABC12...3456
  Chunk 1/6: Found 2 context(s)
  ...
  Mapped 8 contexts
  💾 Saving context mapping to cache...
  ✅ Context mapping cached
```

### Regeneration (With Cache)
```
Starting smart summarization for session abc123...
  ✅ Loading cached context mapping...
  Loaded 8 contexts from cache (meeting type: INCIDENT_REPORT)
  
  Generating notes for context 1/8: Opening Discussion
  📝 Prompting AI: Generating notes for 'Opening Discussion'...
  🔑 Using API key: AIzaSyDEF45...7890
  ...
```

### Meeting Type Changed
```
Starting smart summarization for session abc123...
  🔄 Meeting type changed (REGULAR_MEETING → INCIDENT_REPORT), regenerating contexts...
  
Mapping contexts across 6 chunks...
  📝 Prompting AI: Mapping contexts for chunk 1/6...
  ...
```

---

## Benefits

### 💰 Cost Savings
**Example: 1-hour meeting, 8 contexts**

**First generation:**
- Meeting type detection: 1 call
- Context mapping (6 chunks): 6 calls
- Section notes (8 contexts): 8 calls
- Final summary: 1 call
- **Total: 16 API calls**

**Regeneration (cached):**
- Context mapping: 0 calls (cached!)
- Section notes (8 contexts): 8 calls
- Final summary: 1 call
- **Total: 9 API calls**

**Savings: 7 API calls (44% reduction!)**

### ⚡ Speed Improvement
- **First generation:** ~2-3 minutes
- **Regeneration:** ~1-2 minutes
- **Improvement: 50% faster!**

### 🎯 Consistency
- Same contexts used across regenerations
- Consistent section boundaries
- Easier to compare different meeting types

---

## Use Cases

### 1. Try Different Meeting Types
```
1. Generate as "Auto" → Detects as Regular Meeting
2. Review output
3. Regenerate as "Incident Report" → Uses cached contexts, new format
4. Compare results
```

### 2. Refine Summary
```
1. Generate initial summary
2. Review sections
3. Regenerate with same type → Faster, uses cache
4. Get new AI interpretation of same contexts
```

### 3. Export Multiple Formats
```
1. Generate once
2. Export as Markdown
3. Regenerate (uses cache)
4. Export as JSON
```

---

## Cache Management

### View Cache
```bash
# List all context cache files
ls sessions/*_contexts.json

# View specific cache
cat sessions/abc123_contexts.json
```

### Clear Cache
```bash
# Clear specific session cache
rm sessions/abc123_contexts.json

# Clear all context caches
rm sessions/*_contexts.json
```

### Cache Location
```
transcriber/
├── sessions/
│   ├── abc123.json              # Session data
│   ├── abc123_contexts.json     # Context cache ✨
│   ├── def456.json
│   └── def456_contexts.json     # Context cache ✨
└── summaries/
    ├── abc123_summary.json
    └── def456_summary.json
```

---

## Technical Details

### Cache Structure
- **Format:** JSON
- **Encoding:** UTF-8
- **Size:** ~5-20 KB per session
- **Lifetime:** Permanent (until deleted)

### Cache Validation
- Meeting type is checked on regeneration
- If type changes, cache is regenerated
- No expiration time (contexts don't change)

### Thread Safety
- Cache read/write is synchronous
- No race conditions (single-threaded Flask)
- Safe for concurrent requests

---

## Best Practices

### ✅ Do
- Let cache build naturally
- Use "Auto" for first generation
- Regenerate to try different types
- Keep cache for frequently accessed sessions

### ❌ Don't
- Don't manually edit cache files
- Don't rely on cache for critical data
- Don't commit cache to git (already gitignored)
- Don't worry about cache size (very small)

---

## Troubleshooting

### Cache Not Loading
**Symptom:** Always regenerates contexts
**Solution:** Check if `{session_id}_contexts.json` exists in `sessions/` folder

### Wrong Meeting Type
**Symptom:** Cache has wrong meeting type
**Solution:** Regenerate with specific type (not "Auto")

### Corrupted Cache
**Symptom:** JSON parse errors
**Solution:** Delete cache file, will regenerate automatically

### Old Cache Data
**Symptom:** Want fresh context mapping
**Solution:** Delete cache file before regenerating

---

## Summary

✅ **Automatic caching** - No configuration needed  
✅ **Smart reuse** - Only regenerates when necessary  
✅ **Cost savings** - 44% fewer API calls on regeneration  
✅ **Speed boost** - 50% faster regeneration  
✅ **Type flexibility** - Easy to try different meeting types  
✅ **Consistent results** - Same contexts across regenerations  

The context caching system makes your transcriber faster, cheaper, and more efficient! 🚀
