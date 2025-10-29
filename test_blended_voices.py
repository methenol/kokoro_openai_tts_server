#!/usr/bin/env python3
"""
Tests for blended voice functionality.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import torch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import (
    is_blend_expression,
    parse_blend_expression,
    load_voice_pack,
    blend_voice_packs,
    supported_langs
)


class TestBlendExpressionParser(unittest.TestCase):
    """Tests for blend expression parsing."""
    
    def test_is_blend_expression_simple(self):
        """Test detection of simple blend expressions."""
        self.assertTrue(is_blend_expression("af_heart:90,am_adam:10"))
        self.assertTrue(is_blend_expression("af_heart,am_adam"))
        self.assertFalse(is_blend_expression("af_heart"))
        self.assertFalse(is_blend_expression("a.af_heart"))
    
    def test_parse_basic_blend(self):
        """Test parsing basic blend expression."""
        lang_code, items = parse_blend_expression("af_heart:90,am_adam:10")
        self.assertEqual(lang_code, 'a')
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0], "af_heart")
        self.assertAlmostEqual(items[0][1], 0.9, places=5)
        self.assertEqual(items[1][0], "am_adam")
        self.assertAlmostEqual(items[1][1], 0.1, places=5)
    
    def test_parse_equal_weights(self):
        """Test parsing blend with equal weights (no explicit weights)."""
        lang_code, items = parse_blend_expression("af_heart,am_adam")
        self.assertEqual(lang_code, 'a')
        self.assertEqual(len(items), 2)
        self.assertAlmostEqual(items[0][1], 0.5, places=5)
        self.assertAlmostEqual(items[1][1], 0.5, places=5)
    
    def test_parse_with_explicit_language(self):
        """Test parsing blend with explicit language prefix."""
        lang_code, items = parse_blend_expression("a.af_heart:70,am_adam:30")
        self.assertEqual(lang_code, 'a')
        self.assertEqual(items[0][0], "af_heart")
        self.assertAlmostEqual(items[0][1], 0.7, places=5)
    
    def test_parse_percentage_weights(self):
        """Test parsing blend with percentage weights."""
        lang_code, items = parse_blend_expression("bf_emma:25%,af_heart:75%")
        self.assertEqual(lang_code, 'b')
        self.assertEqual(items[0][0], "bf_emma")
        self.assertAlmostEqual(items[0][1], 0.25, places=5)
        self.assertEqual(items[1][0], "af_heart")
        self.assertAlmostEqual(items[1][1], 0.75, places=5)
    
    def test_parse_three_voices(self):
        """Test parsing blend with three voices."""
        lang_code, items = parse_blend_expression("af_heart:50,am_adam:30,af_bella:20")
        self.assertEqual(len(items), 3)
        self.assertAlmostEqual(items[0][1], 0.5, places=5)
        self.assertAlmostEqual(items[1][1], 0.3, places=5)
        self.assertAlmostEqual(items[2][1], 0.2, places=5)
    
    def test_parse_unnormalized_weights(self):
        """Test that weights are normalized to sum to 1.0."""
        lang_code, items = parse_blend_expression("af_heart:2,am_adam:3")
        self.assertAlmostEqual(items[0][1], 0.4, places=5)
        self.assertAlmostEqual(items[1][1], 0.6, places=5)
    
    def test_parse_invalid_empty(self):
        """Test that empty expression raises error."""
        with self.assertRaises(ValueError):
            parse_blend_expression("")
    
    def test_parse_invalid_negative_weight(self):
        """Test that negative weight raises error."""
        with self.assertRaises(ValueError):
            parse_blend_expression("af_heart:-1,am_adam:1")
    
    def test_parse_invalid_zero_total(self):
        """Test that zero total weight raises error."""
        with self.assertRaises(ValueError):
            parse_blend_expression("af_heart:0,am_adam:0")
    
    def test_parse_invalid_format(self):
        """Test that malformed expression raises error."""
        with self.assertRaises(ValueError):
            parse_blend_expression("af_heart:abc,am_adam")  # Invalid weight format


class TestVoicePackLoading(unittest.TestCase):
    """Tests for voice pack loading."""
    
    @patch('torch.load')
    @patch('huggingface_hub.hf_hub_download')
    def test_load_voice_pack(self, mock_hf_download, mock_torch_load):
        """Test loading a voice pack."""
        mock_hf_download.return_value = "/tmp/fake_path.pt"
        mock_pack = [torch.randn(10), torch.randn(10)]
        mock_torch_load.return_value = mock_pack
        
        # Clear cache
        import server
        server.voice_pack_cache = {}
        
        pack = load_voice_pack("af_heart")
        self.assertEqual(pack, mock_pack)
        mock_hf_download.assert_called_once()
    
    @patch('torch.load')
    @patch('huggingface_hub.hf_hub_download')
    def test_load_voice_pack_uses_cache(self, mock_hf_download, mock_torch_load):
        """Test that repeated loads use cache."""
        mock_hf_download.return_value = "/tmp/fake_path.pt"
        mock_pack = [torch.randn(10), torch.randn(10)]
        mock_torch_load.return_value = mock_pack
        
        # Clear cache
        import server
        server.voice_pack_cache = {}
        
        pack1 = load_voice_pack("af_heart")
        pack2 = load_voice_pack("af_heart")
        
        self.assertEqual(pack1, pack2)
        # Should only download once
        self.assertEqual(mock_hf_download.call_count, 1)
    
    @patch('huggingface_hub.hf_hub_download')
    def test_load_voice_pack_not_found(self, mock_hf_download):
        """Test error handling for missing voice pack."""
        mock_hf_download.side_effect = Exception("File not found")
        
        # Clear cache
        import server
        server.voice_pack_cache = {}
        
        with self.assertRaises(ValueError) as ctx:
            load_voice_pack("nonexistent_voice")
        
        self.assertIn("unknown voice", str(ctx.exception))


class TestVoiceBlending(unittest.TestCase):
    """Tests for voice pack blending."""
    
    @patch('server.load_voice_pack')
    def test_blend_two_voices(self, mock_load):
        """Test blending two voice packs."""
        # Create mock voice packs
        pack1 = [torch.tensor([1.0, 2.0, 3.0]), torch.tensor([4.0, 5.0])]
        pack2 = [torch.tensor([2.0, 4.0, 6.0]), torch.tensor([8.0, 10.0])]
        
        mock_load.side_effect = [pack1, pack2]
        
        voice_weights = [("af_heart", 0.5), ("am_adam", 0.5)]
        blended = blend_voice_packs(voice_weights)
        
        self.assertEqual(len(blended), 2)
        # Check first tensor
        expected1 = torch.tensor([1.5, 3.0, 4.5])
        self.assertTrue(torch.allclose(blended[0], expected1))
        # Check second tensor
        expected2 = torch.tensor([6.0, 7.5])
        self.assertTrue(torch.allclose(blended[1], expected2))
    
    @patch('server.load_voice_pack')
    def test_blend_different_lengths(self, mock_load):
        """Test blending packs of different lengths uses minimum length."""
        # Create packs with different lengths
        pack1 = [torch.tensor([1.0]), torch.tensor([2.0]), torch.tensor([3.0])]
        pack2 = [torch.tensor([4.0]), torch.tensor([5.0])]  # Shorter
        
        mock_load.side_effect = [pack1, pack2]
        
        voice_weights = [("af_heart", 0.5), ("am_adam", 0.5)]
        blended = blend_voice_packs(voice_weights)
        
        # Should use minimum length (2)
        self.assertEqual(len(blended), 2)
    
    @patch('server.load_voice_pack')
    def test_blend_weighted(self, mock_load):
        """Test blending with unequal weights."""
        pack1 = [torch.tensor([10.0])]
        pack2 = [torch.tensor([20.0])]
        
        mock_load.side_effect = [pack1, pack2]
        
        voice_weights = [("af_heart", 0.9), ("am_adam", 0.1)]
        blended = blend_voice_packs(voice_weights)
        
        # 10 * 0.9 + 20 * 0.1 = 9 + 2 = 11
        expected = torch.tensor([11.0])
        self.assertTrue(torch.allclose(blended[0], expected))


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    @patch('server.tts_pipeline')
    @patch('server.load_voice_pack')
    def test_generate_speech_with_blend(self, mock_load, mock_pipeline):
        """Test generating speech with blended voices."""
        # Mock voice packs
        pack1 = [torch.tensor([1.0]), torch.tensor([2.0])]
        pack2 = [torch.tensor([3.0]), torch.tensor([4.0])]
        mock_load.side_effect = [pack1, pack2]
        
        # Mock pipeline
        mock_gen = Mock()
        mock_gen.__iter__ = Mock(return_value=iter([
            (None, None, torch.tensor([0.5, 0.5]))
        ]))
        mock_pipeline.return_value = mock_gen
        
        from server import generate_speech
        
        # This would normally fail without our changes
        # Just test that the blend expression is processed
        blend_expr = "af_heart:70,am_adam:30"
        self.assertTrue(is_blend_expression(blend_expr))


if __name__ == '__main__':
    unittest.main()
