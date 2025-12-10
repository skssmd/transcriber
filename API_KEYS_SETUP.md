# API Keys Setup Guide

## Quick Setup

### Step 1: Create settings.py

Copy the example file:
```bash
cp settings.example.py settings.py
```

Or on Windows:
```bash
copy settings.example.py settings.py
```

### Step 2: Add Your API Keys

Open `settings.py` and add your Gemini API keys:

```python
# settings.py
GEMINI_API_KEYS = [
    "AIzaSyBRFKZNhVFBd6xdiItADwsj2-mUhh-YfWU",  # Your first key
    "AIzaSyABC123...",  # Add more keys here
    "AIzaSyDEF456...",
    "AIzaSyGHI789...",
    "AIzaSyJKL012...",
]
```

### Step 3: Run the App

```bash
python app.py
```

You should see:
```
Loaded 5 API key(s) from settings.py
```

---

## Why Multiple Keys?

### Benefits:
- **5x Rate Limit Capacity**: Each key has its own rate limit
- **Load Distribution**: Requests spread across all keys
- **Reliability**: If one key hits limit, others continue working
- **Faster Processing**: More concurrent requests possible

### Example:
- 1 key: 60 requests/minute
- 5 keys: 300 requests/minute effective limit

---

## File Structure

```
transcriber/
├── settings.py              # Your actual keys (gitignored)
├── settings.example.py      # Template (committed to git)
├── app.py                   # Imports from settings.py
└── .gitignore              # Ignores settings.py
```

---

## Security

✅ **settings.py is gitignored** - Your keys won't be committed to git

✅ **settings.example.py is committed** - Template for other users

✅ **Local project only** - Keys stay on your machine

---

## Alternative: Environment Variables

If you prefer environment variables instead:

### Windows:
```bash
set GEMINI_API_KEYS=key1,key2,key3,key4,key5
python app.py
```

### Linux/Mac:
```bash
export GEMINI_API_KEYS=key1,key2,key3,key4,key5
python app.py
```

The app will automatically use environment variables if `settings.py` doesn't exist.

---

## Troubleshooting

### No API keys found
```
WARNING: No API keys found. Please create settings.py or set GEMINI_API_KEYS environment variable
```

**Solution**: Create `settings.py` from the template and add your keys.

### Import error
```
ImportError: cannot import name 'GEMINI_API_KEYS' from 'settings'
```

**Solution**: Make sure `settings.py` has the `GEMINI_API_KEYS` list defined.

### Keys not rotating
**Solution**: Check that you have multiple keys in the list and they're all valid.

---

## Getting Gemini API Keys

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key
4. Repeat to create multiple keys
5. Add all keys to `settings.py`

---

## Best Practices

1. **Use 5 keys** for optimal performance
2. **Keep settings.py private** - Never commit it
3. **Rotate keys** if any hit limits
4. **Monitor usage** in Google Cloud Console
5. **Test with one key first** before adding more

---

## Summary

✅ Create `settings.py` from template  
✅ Add your API keys to the list  
✅ Run the app  
✅ Keys automatically rotate  
✅ Enjoy 5x rate limit capacity!
