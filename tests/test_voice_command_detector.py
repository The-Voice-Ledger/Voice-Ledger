"""
Voice Command Detector Tests

Tests the pattern matching system that detects commands in voice transcripts.
"""

import pytest
from voice.tasks.voice_command_detector import detect_voice_command, get_command_help_text


class TestVoiceCommandDetection:
    """Test suite for voice command pattern matching"""
    
    def test_start_command_variations(self):
        """Test various ways to say 'start'"""
        test_cases = [
            "start",
            "hi",
            "hello",
            "hey",
            "begin",
            "Start",  # Case insensitive
            "HELLO",
            "start please",
            "hi there"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect start command in: '{transcript}'"
            assert result['command'] == 'start', f"Wrong command for '{transcript}'"
            assert result['status'] == 'voice_command'
    
    def test_help_command_variations(self):
        """Test various ways to ask for help"""
        test_cases = [
            "help",
            "help me",
            "I need help",
            "assist",
            "support",
            "commands",
            "what can you do",
            "Help please"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect help command in: '{transcript}'"
            assert result['command'] == 'help', f"Wrong command for '{transcript}'"
    
    def test_register_command_variations(self):
        """Test various ways to say 'register'"""
        test_cases = [
            "register",
            "I want to register",
            "sign up",
            "signup",
            "join",
            "enroll",
            "Register me please"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect register command in: '{transcript}'"
            assert result['command'] == 'register', f"Wrong command for '{transcript}'"
    
    def test_status_command_variations(self):
        """Test various ways to check status"""
        test_cases = [
            "status",
            "health",
            "check status",
            "system status"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect status command in: '{transcript}'"
            assert result['command'] == 'status', f"Wrong command for '{transcript}'"
    
    def test_myidentity_command_variations(self):
        """Test various ways to request identity"""
        test_cases = [
            "show my identity",
            "show me my identity",
            "display my identity",
            "get my identity",
            "view my identity",
            "show my did",
            "what is my DID",
            "show me my DID"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect myidentity command in: '{transcript}'"
            assert result['command'] == 'myidentity', f"Wrong command for '{transcript}'"
    
    def test_mybatches_command_variations(self):
        """Test various ways to request batch list"""
        test_cases = [
            "show my batches",
            "show me my batches",
            "display my batches",
            "get my batches",
            "list my batches",
            "view my batches",
            "show my batch",
            "show my coffee",
            "list my coffee"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect mybatches command in: '{transcript}'"
            assert result['command'] == 'mybatches', f"Wrong command for '{transcript}'"
    
    def test_mycredentials_command_variations(self):
        """Test various ways to request credentials"""
        test_cases = [
            "show my credentials",
            "show me my credentials",
            "display my credentials",
            "get my credentials",
            "view my credential"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect mycredentials command in: '{transcript}'"
            assert result['command'] == 'mycredentials', f"Wrong command for '{transcript}'"
    
    def test_export_command_variations(self):
        """Test various ways to trigger export"""
        test_cases = [
            "export",
            "download",
            "export my data",
            "download my data"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed to detect export command in: '{transcript}'"
            assert result['command'] == 'export', f"Wrong command for '{transcript}'"
    
    def test_non_command_phrases(self):
        """Test that regular conversation doesn't trigger commands"""
        non_command_phrases = [
            "I want to create a new batch",
            "I received 50 kg of coffee",
            "The shipment arrived yesterday",
            "I need to commission a new batch of Sidama coffee",
            "Can you transform my batch?",
            "The cooperative meeting is next week",
            "I sold 100 kg to an exporter",
            "What is the current price?"
        ]
        
        for transcript in non_command_phrases:
            result = detect_voice_command(transcript, {})
            assert result is None, f"False positive: '{transcript}' should not trigger a command"
    
    def test_empty_transcript(self):
        """Test handling of empty transcript"""
        result = detect_voice_command("", {})
        assert result is None
        
        result = detect_voice_command(None, {})
        assert result is None
    
    def test_metadata_passthrough(self):
        """Test that metadata is passed through correctly"""
        metadata = {
            "channel": "telegram",
            "user_id": 12345,
            "message_id": 67890
        }
        
        result = detect_voice_command("help", metadata)
        assert result is not None
        assert result['metadata'] == metadata
    
    def test_transcript_preservation(self):
        """Test that original transcript is preserved"""
        transcript = "Hello, I need HELP please!"
        result = detect_voice_command(transcript, {})
        assert result is not None
        assert result['transcript'] == transcript
    
    def test_case_insensitivity(self):
        """Test that command detection is case-insensitive"""
        test_cases = [
            ("START", "start"),
            ("Help", "help"),
            ("REGISTER", "register"),
            ("Show My Identity", "myidentity"),
            ("SHOW MY BATCHES", "mybatches")
        ]
        
        for transcript, expected_command in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed for '{transcript}'"
            assert result['command'] == expected_command
    
    def test_command_with_noise(self):
        """Test command detection with surrounding noise words"""
        test_cases = [
            ("um, help me please", "help"),
            ("uh, I want to register", "register"),
            ("so, show my batches", "mybatches"),
            ("well, hello there", "start"),
            ("okay, status check", "status")
        ]
        
        for transcript, expected_command in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed for '{transcript}'"
            assert result['command'] == expected_command
    
    def test_priority_matching(self):
        """Test that more specific patterns match before generic ones"""
        # "show my identity" should match myidentity, not just identity
        result = detect_voice_command("show my identity", {})
        assert result['command'] == 'myidentity'
        
        # "show my batches" should match mybatches, not just batches
        result = detect_voice_command("show my batches", {})
        assert result['command'] == 'mybatches'


class TestCommandHelpText:
    """Test suite for command help text generation"""
    
    def test_help_text_generation(self):
        """Test that help text is generated correctly"""
        help_text = get_command_help_text()
        
        assert help_text is not None
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        
        # Check that key commands are mentioned
        assert "start" in help_text.lower() or "hello" in help_text.lower()
        assert "help" in help_text.lower()
        assert "register" in help_text.lower()
        assert "identity" in help_text.lower()
        assert "batches" in help_text.lower()


class TestAmharicSupport:
    """Test suite for potential Amharic command support"""
    
    def test_english_commands_work(self):
        """Verify English commands still work (baseline)"""
        result = detect_voice_command("help", {})
        assert result is not None
        assert result['command'] == 'help'
    
    @pytest.mark.skip(reason="Amharic patterns not yet implemented")
    def test_amharic_commands(self):
        """Test Amharic command patterns (future feature)"""
        # Example Amharic phrases that could be added:
        amharic_tests = [
            ("እርዳታ", "help"),  # erdeta = help
            ("መመዝገብ", "register"),  # mezmegeb = register
            ("ሁኔታ", "status"),  # huneta = status
        ]
        
        for transcript, expected_command in amharic_tests:
            result = detect_voice_command(transcript, {})
            assert result is not None
            assert result['command'] == expected_command


class TestEdgeCases:
    """Test suite for edge cases and error conditions"""
    
    def test_very_long_transcript(self):
        """Test handling of very long transcripts"""
        long_transcript = "help " * 1000
        result = detect_voice_command(long_transcript, {})
        assert result is not None
        assert result['command'] == 'help'
    
    def test_whitespace_variations(self):
        """Test handling of various whitespace"""
        test_cases = [
            "  help  ",
            "\thelp\t",
            "\nhelp\n",
            "help   me",
            "show    my    batches"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Failed for: '{repr(transcript)}'"
    
    def test_special_characters(self):
        """Test handling of special characters"""
        test_cases = [
            "help!",
            "help?",
            "help.",
            "help,",
            "show my identity!",
            "register?"
        ]
        
        for transcript in test_cases:
            result = detect_voice_command(transcript, {})
            # Should still detect commands despite special characters
            assert result is not None, f"Failed for '{transcript}'"
    
    def test_numbers_in_transcript(self):
        """Test that numbers don't interfere with detection"""
        test_cases = [
            ("help 123", "help"),
            ("show my 5 batches", "mybatches"),
            ("register 2024", "register")
        ]
        
        for transcript, expected_command in test_cases:
            result = detect_voice_command(transcript, {})
            assert result is not None
            assert result['command'] == expected_command


class TestIntegrationScenarios:
    """Test real-world usage scenarios"""
    
    def test_cooperative_farmer_workflow(self):
        """Test typical commands a cooperative farmer might use"""
        workflow = [
            ("hello", "start"),
            ("I want to register", "register"),
            ("show my batches", "mybatches"),
            ("what is my identity", "myidentity"),
            ("help", "help")
        ]
        
        for transcript, expected_command in workflow:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Workflow failed at: '{transcript}'"
            assert result['command'] == expected_command
    
    def test_buyer_workflow(self):
        """Test typical commands a buyer might use"""
        workflow = [
            ("hi", "start"),
            ("register", "register"),
            ("show my credentials", "mycredentials"),
            ("export my data", "export"),
            ("status", "status")
        ]
        
        for transcript, expected_command in workflow:
            result = detect_voice_command(transcript, {})
            assert result is not None, f"Workflow failed at: '{transcript}'"
            assert result['command'] == expected_command
    
    def test_mixed_commands_and_operations(self):
        """Test alternating between commands and batch operations"""
        inputs = [
            ("hello", True, "start"),  # Command
            ("I need to create a new batch", False, None),  # Operation
            ("show my batches", True, "mybatches"),  # Command
            ("ship 50 kg to Addis", False, None),  # Operation
            ("help", True, "help")  # Command
        ]
        
        for transcript, should_detect, expected_command in inputs:
            result = detect_voice_command(transcript, {})
            if should_detect:
                assert result is not None, f"Should detect command in: '{transcript}'"
                assert result['command'] == expected_command
            else:
                assert result is None, f"Should NOT detect command in: '{transcript}'"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])
