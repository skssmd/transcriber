
import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Ensure we can import app
sys.path.append(os.getcwd())
# Mock settings.GEMINI_API_KEYS before importing app
sys.modules['settings'] = MagicMock()
sys.modules['settings'].GEMINI_API_KEYS = ['fake_key']

from app import process_chunk_stream

class TestStreamProcessing(unittest.TestCase):
    def setUp(self):
        self.segments = [
            {'start': 0, 'end': 500, 'text': 'Segment 1'},
            {'start': 500, 'end': 1000, 'text': 'Segment 2'}, # Should fall into second chunk
            {'start': 1000, 'end': 1500, 'text': 'Segment 3'}
        ]
        
    @patch('app.get_model')
    @patch('app.chunk_by_time')
    @patch('app.get_segments_text')
    def test_ongoing_context_logic(self, mock_get_text, mock_chunk, mock_get_model):
        # Setup mocks
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model
        mock_get_text.return_value = "Mock Text"
        
        # Simulate 2 chunks
        chunks = [
            {'start_time': 0, 'end_time': 900, 'segments': []},
            {'start_time': 900, 'end_time': 1800, 'segments': []} 
        ]
        mock_chunk.return_value = chunks
        
        # Responses for the 2 chunks
        response1 = MagicMock()
        response1.text = json.dumps([
            {
                "name": "Topic A",
                "from_time": 0,
                "end_time": 900,
                "status": "ongoing",
                "notes": ["Note 1"]
            }
        ])
        
        response2 = MagicMock()
        response2.text = json.dumps([
            {
                "name": "Topic A", # Continued
                "from_time": 900, # Starts where last one ended (roughly)
                "end_time": 1000, 
                "status": "finished",
                "notes": ["Note 2"] # Only NEW notes
            },
            {
                "name": "Topic B",
                "from_time": 1000,
                "end_time": 1800,
                "status": "ongoing",
                "notes": ["Note 3"]
            }
        ])
        
        mock_model.generate_content.side_effect = [response1, response2]
        
        # Run
        result = process_chunk_stream(self.segments, mock_model)
        
        # Assertions
        print("\nResult Sections:", json.dumps(result, indent=2))
        
        self.assertEqual(len(result), 2)
        
        # Verify Topic A
        topic_a = next(r for r in result if r['section_name'] == "Topic A")
        self.assertEqual(topic_a['start_time'], 0.0)
        self.assertEqual(topic_a['end_time'], 1000.0)
        self.assertEqual(len(topic_a['notes']), 2)
        self.assertIn("Note 1", topic_a['notes'])
        self.assertIn("Note 2", topic_a['notes'])
        
        # Verify Topic B (was left 'ongoing' at end of chunk 2, should be closed automatically)
        topic_b = next(r for r in result if r['section_name'] == "Topic B")
        self.assertEqual(topic_b['start_time'], 1000.0)
        self.assertEqual(topic_b['end_time'], 1800.0)
        
        print("\n✅ Verification Successful: Logic handles context transitions and merging correctly.")

if __name__ == '__main__':
    unittest.main()
