import unittest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime, timezone

from scripts.csr_generation_agent import (
    CSRSection, TLFType, TLFItem, BoilerplateText, ProtocolInfo, CSRDocument,
    load_protocol_info, create_default_protocol_info, load_tlf_items,
    load_boilerplate_library, create_default_boilerplate_library,
    generate_section_content, substitute_placeholders, insert_tlf_references,
    generate_csr_document, save_csr_document, update_checklist, write_progress_log
)


class TestCSRGenerationAgent(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_protocol_info = ProtocolInfo(
            protocol_number="TEST-001",
            protocol_title="Test Protocol",
            sponsor="Test Sponsor",
            indication="Test Indication",
            study_phase="Phase II",
            study_design="Randomized, Double-blind",
            primary_objectives=["Primary objective 1"],
            secondary_objectives=["Secondary objective 1"],
            primary_endpoints=["Primary endpoint 1"],
            secondary_endpoints=["Secondary endpoint 1"],
            study_population="Adult patients",
            sample_size=100,
            study_duration="12 months"
        )
        
        self.test_tlf_items = [
            TLFItem(
                tlf_id="T_01",
                title="Demographics Table",
                tlf_type=TLFType.TABLE,
                file_path="/path/to/demographics.html",
                section_reference=CSRSection.STUDY_SUBJECTS,
                description="Demographics and baseline characteristics"
            ),
            TLFItem(
                tlf_id="F_01",
                title="Efficacy Figure",
                tlf_type=TLFType.FIGURE,
                file_path="/path/to/efficacy.png",
                section_reference=CSRSection.EFFICACY_EVALUATION,
                description="Primary efficacy results"
            )
        ]
        
        self.test_boilerplate = BoilerplateText(
            section=CSRSection.SYNOPSIS,
            content="Test synopsis with {protocol_number}",
            placeholders=["protocol_number"]
        )

    def test_load_protocol_info_success(self):
        """Test successful loading of protocol info."""
        protocol_data = {
            "protocol_number": "PROTO-123",
            "protocol_title": "Test Protocol Title",
            "sponsor": "Test Sponsor",
            "indication": "Test Indication",
            "study_phase": "Phase III",
            "study_design": "Randomized",
            "primary_objectives": ["Objective 1"],
            "secondary_objectives": ["Objective 2"],
            "primary_endpoints": ["Endpoint 1"],
            "secondary_endpoints": ["Endpoint 2"],
            "study_population": "Adults",
            "sample_size": 200,
            "study_duration": "24 months"
        }
        
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(protocol_data))):
            result = load_protocol_info("test_file.json")
            
            self.assertEqual(result.protocol_number, "PROTO-123")
            self.assertEqual(result.protocol_title, "Test Protocol Title")
            self.assertEqual(result.sample_size, 200)

    def test_load_protocol_info_file_not_found(self):
        """Test loading protocol info when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            result = load_protocol_info("nonexistent_file.json")
            
            self.assertEqual(result.protocol_number, "PROTO-001")
            self.assertEqual(result.protocol_title, "Clinical Trial Protocol")

    def test_create_default_protocol_info(self):
        """Test creation of default protocol info."""
        result = create_default_protocol_info()
        
        self.assertEqual(result.protocol_number, "PROTO-001")
        self.assertEqual(result.sponsor, "Sponsor Name")
        self.assertEqual(result.sample_size, 100)
        self.assertIsInstance(result.primary_objectives, list)

    def test_load_tlf_items_with_catalog(self):
        """Test loading TLF items from catalog file."""
        catalog_data = {
            "tlf_items": [
                {
                    "tlf_id": "T_01",
                    "title": "Demographics",
                    "tlf_type": "table",
                    "file_path": "demographics.html",
                    "section_reference": "study_subjects",
                    "description": "Demographics table"
                }
            ]
        }
        
        with patch("os.path.exists") as mock_exists, \
             patch("builtins.open", mock_open(read_data=json.dumps(catalog_data))):
            mock_exists.side_effect = lambda path: "tlf_catalog.json" in path
            
            result = load_tlf_items("test_dir")
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].tlf_id, "T_01")
            self.assertEqual(result[0].title, "Demographics")
            self.assertEqual(result[0].tlf_type, TLFType.TABLE)

    def test_load_tlf_items_directory_scan(self):
        """Test loading TLF items by scanning directory."""
        with patch("os.path.exists", return_value=True), \
             patch("pathlib.Path.rglob") as mock_rglob:
            
            mock_file = MagicMock()
            mock_file.is_file.return_value = True
            mock_file.suffix.lower.return_value = ".html"
            mock_file.stem = "t_demographics"
            mock_rglob.return_value = [mock_file]
            
            result = load_tlf_items("test_dir")
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].tlf_type, TLFType.TABLE)

    def test_load_boilerplate_library_success(self):
        """Test successful loading of boilerplate library."""
        boilerplate_data = {
            "synopsis": {
                "content": "Test synopsis content {protocol_number}",
                "placeholders": ["protocol_number"],
                "is_template": True
            }
        }
        
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(boilerplate_data))):
            result = load_boilerplate_library("test_file.json")
            
            self.assertIn(CSRSection.SYNOPSIS, result)
            self.assertEqual(result[CSRSection.SYNOPSIS].content, "Test synopsis content {protocol_number}")

    def test_load_boilerplate_library_file_not_found(self):
        """Test loading boilerplate library when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            result = load_boilerplate_library("nonexistent_file.json")
            
            self.assertIsInstance(result, dict)
            self.assertIn(CSRSection.SYNOPSIS, result)

    def test_create_default_boilerplate_library(self):
        """Test creation of default boilerplate library."""
        result = create_default_boilerplate_library()
        
        self.assertIsInstance(result, dict)
        self.assertIn(CSRSection.SYNOPSIS, result)
        self.assertIn(CSRSection.INTRODUCTION, result)
        self.assertIn(CSRSection.STUDY_OBJECTIVES, result)

    @patch('scripts.csr_generation_agent.get_llm_model_name')
    @patch('scripts.csr_generation_agent.completion')
    def test_generate_section_content_with_llm(self, mock_completion, mock_get_model):
        """Test generating section content with LLM."""
        mock_get_model.return_value = "gpt-3.5-turbo"
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Generated content for {protocol_number}"
        mock_completion.return_value = mock_response
        
        result = generate_section_content(
            CSRSection.SYNOPSIS, 
            self.test_protocol_info, 
            self.test_boilerplate, 
            self.test_tlf_items
        )
        
        self.assertIn("TEST-001", result)
        mock_completion.assert_called_once()

    @patch('scripts.csr_generation_agent.get_llm_model_name')
    def test_generate_section_content_without_llm(self, mock_get_model):
        """Test generating section content without LLM."""
        mock_get_model.return_value = None
        
        result = generate_section_content(
            CSRSection.SYNOPSIS, 
            self.test_protocol_info, 
            self.test_boilerplate, 
            self.test_tlf_items
        )
        
        self.assertIn("TEST-001", result)

    @patch('scripts.csr_generation_agent.get_llm_model_name')
    @patch('scripts.csr_generation_agent.completion')
    def test_generate_section_content_llm_error(self, mock_completion, mock_get_model):
        """Test generating section content when LLM fails."""
        mock_get_model.return_value = "gpt-3.5-turbo"
        mock_completion.side_effect = Exception("LLM Error")
        
        result = generate_section_content(
            CSRSection.SYNOPSIS, 
            self.test_protocol_info, 
            self.test_boilerplate, 
            self.test_tlf_items
        )
        
        self.assertIn("TEST-001", result)

    def test_substitute_placeholders(self):
        """Test placeholder substitution."""
        content = "Protocol {protocol_number} for {indication}"
        
        result = substitute_placeholders(content, self.test_protocol_info, self.test_tlf_items)
        
        self.assertIn("TEST-001", result)
        self.assertIn("Test Indication", result)
        self.assertNotIn("{protocol_number}", result)

    def test_insert_tlf_references(self):
        """Test TLF reference insertion."""
        content = "See [TABLE: Demographics Table] and [FIGURE: Efficacy Figure]"
        
        result = insert_tlf_references(content, self.test_tlf_items)
        
        self.assertIn("Table 1: Demographics Table", result)
        self.assertIn("Figure 1: Efficacy Figure", result)

    def test_generate_csr_document(self):
        """Test CSR document generation."""
        boilerplate_texts = {
            CSRSection.SYNOPSIS: self.test_boilerplate,
            CSRSection.INTRODUCTION: BoilerplateText(
                section=CSRSection.INTRODUCTION,
                content="Introduction for {protocol_number}",
                placeholders=["protocol_number"]
            )
        }
        
        with patch('scripts.csr_generation_agent.generate_section_content') as mock_gen:
            mock_gen.return_value = "Generated content"
            
            result = generate_csr_document(
                self.test_protocol_info, 
                self.test_tlf_items, 
                boilerplate_texts
            )
            
            self.assertIsInstance(result, CSRDocument)
            self.assertEqual(result.protocol_info, self.test_protocol_info)
            self.assertEqual(result.tlf_items, self.test_tlf_items)
            self.assertIn("generation_date", result.metadata)

    def test_save_csr_document(self):
        """Test saving CSR document."""
        csr_document = CSRDocument(
            protocol_info=self.test_protocol_info,
            sections={CSRSection.SYNOPSIS: "Test content"},
            tlf_items=self.test_tlf_items,
            metadata={"test": "metadata"},
            generation_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_csr_document(csr_document, temp_dir)
            
            self.assertTrue(os.path.exists(result))
            self.assertIn("clinical_study_report", result)
            
            # Check if metadata file was created
            metadata_files = [f for f in os.listdir(temp_dir) if f.startswith("csr_metadata")]
            self.assertEqual(len(metadata_files), 1)

    @patch('builtins.open', new_callable=mock_open, read_data='[]')
    @patch('yaml.safe_load')
    @patch('yaml.safe_dump')
    def test_update_checklist(self, mock_dump, mock_load, mock_file):
        """Test updating checklist."""
        mock_load.return_value = [{"agentId": "4.300", "status": 0}]
        
        update_checklist("test_checklist.yml", 100)
        
        mock_dump.assert_called_once()
        args, kwargs = mock_dump.call_args
        self.assertEqual(args[0][0]["status"], 100)

    def test_write_progress_log(self):
        """Test writing progress log."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = write_progress_log(temp_dir, 100, "Test summary")
            
            self.assertTrue(os.path.exists(result))
            self.assertIn("4.300-100-", result)
            
            with open(result, 'r') as f:
                log_data = json.load(f)
                self.assertEqual(log_data["agentId"], "4.300")
                self.assertEqual(log_data["status"], 100)
                self.assertEqual(log_data["summary"], "Test summary")


if __name__ == '__main__':
    unittest.main()