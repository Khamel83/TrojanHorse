"""Integration tests between TrojanHorse and Atlas APIs."""

import pytest
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import httpx

from ..api_server import app as trojanhorse_app
from ..atlas_client import AtlasClient, promote_notes_from_trojanhorse


class TestTrojanHorseToAtlasIntegration:
    """Test integration flow from TrojanHorse to Atlas."""

    @pytest.fixture
    def trojanhorse_client(self):
        """Create TrojanHorse test client."""
        # Mock app state
        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            with patch('TrojanHorse.api_server.app.state.index_db', Mock()):
                with patch('TrojanHorse.api_server.app.state.rag_index', Mock()):
                    return TestClient(trojanhorse_app)

    @pytest.fixture
    def atlas_mock_client(self):
        """Create mock Atlas client."""
        return Mock(spec=AtlasClient)

    @pytest.fixture
    def sample_integration_note(self):
        """Sample note for integration testing."""
        return {
            "id": "integration-test-123",
            "path": "/Users/user/WorkVault/Processed/work/meetings/2024/integration-test.md",
            "title": "Integration Test Meeting",
            "source": "drafts",
            "raw_type": "meeting_transcript",
            "class_type": "work",
            "category": "meeting",
            "project": "integration-test",
            "tags": ["integration", "test", "meeting"],
            "created_at": "2024-01-15T14:30:00.000Z",
            "updated_at": "2024-01-15T14:35:00.000Z",
            "summary": "Integration test meeting to verify TrojanHorse to Atlas promotion",
            "body": "# Integration Test Meeting\n\n## Purpose\nTest the complete integration flow from TrojanHorse to Atlas.\n\n## Attendees\n- Development Team\n- QA Team\n\n## Discussion\nVerified the promotion workflow and API endpoints.",
            "frontmatter": {
                "meeting_type": "integration_test",
                "duration_minutes": 30,
                "priority": "high"
            }
        }

    def test_full_promotion_workflow(self, trojanhorse_client, atlas_mock_client, sample_integration_note):
        """Test complete promotion workflow from TrojanHorse to Atlas."""
        # Step 1: Get notes from TrojanHorse for promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {
                    "id": "integration-test-123",
                    "title": "Integration Test Meeting",
                    "category": "meeting",
                    "project": "integration-test"
                },
                "body": "# Integration Test Meeting\nContent here"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "integration-test-123",
                    "dest_path": "/test/processed/integration-test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["integration-test-123"]}
                )

        assert promote_response.status_code == 200
        promoted_data = promote_response.json()
        assert "items" in promoted_data
        assert len(promoted_data["items"]) == 1
        assert promoted_data["items"][0]["id"] == "integration-test-123"

        # Step 2: Send to Atlas
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = True

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["integration-test-123"]
        )

        assert count == 1
        atlas_mock_client.health_check.assert_called_once()
        atlas_mock_client.ingest_notes.assert_called_once()

        # Verify the note structure sent to Atlas
        atlas_notes = atlas_mock_client.ingest_notes.call_args[0][0]
        assert len(atlas_notes) == 1
        assert atlas_notes[0]["id"] == "integration-test-123"
        assert atlas_notes[0]["title"] == "Integration Test Meeting"
        assert "Integration test meeting" in atlas_notes[0]["body"]

    def test_batch_promotion_workflow(self, trojanhorse_client, atlas_mock_client):
        """Test batch promotion workflow with multiple notes."""
        note_ids = ["batch-note-1", "batch-note-2", "batch-note-3"]

        # Mock TrojanHorse response for batch promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test", "category": "test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": note_ids}
                )

        assert promote_response.status_code == 200
        promoted_data = promote_response.json()
        assert len(promoted_data["items"]) == 3

        # Step 2: Send batch to Atlas
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = True

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            note_ids
        )

        assert count == 3
        atlas_notes = atlas_mock_client.ingest_notes.call_args[0][0]
        assert len(atlas_notes) == 3

    def test_promotion_with_atlas_unavailable(self, trojanhorse_client, atlas_mock_client):
        """Test promotion when Atlas is not available."""
        atlas_mock_client.health_check.return_value = False

        note_ids = ["test-note-1"]

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            note_ids
        )

        assert count == 0
        atlas_mock_client.health_check.assert_called_once()
        atlas_mock_client.ingest_notes.assert_not_called()

    def test_promotion_with_trojanhorse_error(self, atlas_mock_client):
        """Test promotion when TrojanHorse API fails."""
        note_ids = ["test-note-1"]

        with patch('TrojanHorse.atlas_client.requests.post') as mock_post:
            mock_post.side_effect = Exception("TrojanHorse API error")

            count = promote_notes_from_trojanhorse(
                "http://localhost:8765",
                atlas_mock_client,
                note_ids
            )

        assert count == 0

    def test_promotion_with_atlas_ingest_error(self, trojanhorse_client, atlas_mock_client):
        """Test promotion when Atlas ingestion fails."""
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = False

        # Mock TrojanHorse promotion response
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["test-note-1"]}
                )

        assert promote_response.status_code == 200

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["test-note-1"]
        )

        assert count == 0
        atlas_mock_client.ingest_notes.assert_called_once()


class TestRealAPIIntegration:
    """Test integration with real API endpoints."""

    @pytest.mark.asyncio
    async def test_async_trojanhorse_atlas_communication(self):
        """Test async communication between TrojanHorse and Atlas APIs."""
        # Mock both apps for async testing
        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            with patch('TrojanHorse.api_server.app.state.index_db', Mock()):
                with patch('TrojanHorse.api_server.app.state.rag_index', Mock()):
                    with patch('helpers.simple_database.SimpleDatabase'):
                        async with httpx.AsyncClient(trojanhorse_app, base_url="http://localhost:8765") as th_client:
                            async with httpx.AsyncClient(app, base_url="http://localhost:8787") as atlas_client:
                                # Test TrojanHorse health
                                th_health = await th_client.get("/health")
                                assert th_health.status_code == 200

                                # Test Atlas health
                                atlas_health = await atlas_client.get("/trojanhorse/health")
                                assert atlas_health.status_code == 200

    def test_concurrent_api_requests(self, trojanhorse_client, atlas_mock_client):
        """Test handling concurrent API requests."""
        # Setup successful mocks
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = True

        # Mock TrojanHorse for multiple promotions
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                # Simulate multiple concurrent promotions
                import threading
                import time

                results = []

                def promote_notes(note_ids, result_list):
                    try:
                        count = promote_notes_from_trojanhorse(
                            "http://localhost:8765",
                            atlas_mock_client,
                            note_ids
                        )
                        result_list.append(count)
                    except Exception as e:
                        result_list.append(0)

                # Create multiple threads for concurrent promotions
                threads = []
                for i in range(3):
                    note_ids = [f"concurrent-note-{i}-{j}" for j in range(2)]
                    thread = threading.Thread(
                        target=promote_notes,
                        args=(note_ids, results)
                    )
                    threads.append(thread)
                    thread.start()

                # Wait for all threads to complete
                for thread in threads:
                    thread.join()

                assert len(results) == 3
                assert all(count == 2 for count in results)  # Each has 2 notes

                # Verify Atlas client was called correctly
                assert atlas_mock_client.health_check.call_count == 3
                assert atlas_mock_client.ingest_notes.call_count == 3


class TestErrorRecovery:
    """Test error recovery and resilience."""

    def test_retry_mechanism_simulation(self, trojanhorse_client, atlas_mock_client):
        """Test simulated retry mechanism for failed Atlas calls."""
        # Setup mock to fail first time, succeed second time
        call_count = 0
        def ingest_with_retry(notes):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False  # First call fails
            return True  # Second call succeeds

        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.side_effect = ingest_with_retry

        # Mock TrojanHorse promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["retry-test-note"]}
                )

        # Note: In real implementation, you'd add retry logic here
        # For this test, we simulate the first call failing
        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["retry-test-note"]
        )

        # With current implementation, this would return 0 because we don't have retry logic
        assert count == 0
        assert call_count == 1

    def test_partial_batch_failure_handling(self, trojanhorse_client, atlas_mock_client):
        """Test handling of partial batch failures."""
        # Setup mock to handle mixed success/failure
        def ingest_mixed_results(notes):
            # Simulate first 2 notes succeeding, last one failing
            return len(notes) - 1  # Return success count

        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.side_effect = ingest_mixed_results

        # Mock TrojanHorse batch promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["partial-1", "partial-2", "partial-3"]}
                )

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["partial-1", "partial-2", "partial-3"]
        )

        # With current implementation, this returns 0 because we don't handle partial success
        # In a real implementation, you'd want to track individual note success/failure
        assert count == 0


class TestDataIntegrity:
    """Test data integrity during transfer."""

    def test_note_structure_preservation(self, trojanhorse_client, atlas_mock_client, sample_integration_note):
        """Test that note structure is preserved during transfer."""
        # Mock TrojanHorse promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {
                    "id": "integration-test-123",
                    "title": "Integration Test Meeting",
                    "category": "meeting",
                    "project": "integration-test"
                },
                "body": "# Integration Test Meeting\nContent here"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "integration-test-123",
                    "dest_path": "/test/processed/integration-test.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["integration-test-123"]}
                )

        # Capture the data sent to Atlas
        captured_notes = []

        def ingest_capture(notes):
            captured_notes.extend(notes)
            return True

        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.side_effect = ingest_capture

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["integration-test-123"]
        )

        assert count == 1
        assert len(captured_notes) == 1

        # Verify data integrity
        transferred_note = captured_notes[0]
        assert transferred_note["id"] == sample_integration_note["id"]
        assert transferred_note["title"] == sample_integration_note["title"]
        assert transferred_note["category"] == sample_integration_note["category"]
        assert transferred_note["project"] == sample_integration_note["project"]
        assert transferred_note["tags"] == sample_integration_note["tags"]
        assert transferred_note["body"] == sample_integration_note["body"]
        assert transferred_note["frontmatter"] == sample_integration_note["frontmatter"]

    def test_large_note_transfer(self, trojanhorse_client, atlas_mock_client):
        """Test transfer of large notes with extensive content."""
        large_note = {
            "id": "large-note-test",
            "path": "/test/large-note.md",
            "title": "Large Note with Extensive Content",
            "body": "# Large Note\n\n" + "This is a large note. " * 10000 + "\n" + "More content here. " * 5000,
            "tags": ["large", "extensive", "test"],
            "frontmatter": {"large": True, "word_count": 15000}
        }

        # Mock TrojanHorse promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "large-note-test", "title": "Large Note"},
                "body": large_note["body"]
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "large-note-test",
                    "dest_path": "/test/large-note.md"
                }

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": ["large-note-test"]}
                )

        # Capture transferred data
        transferred_note = None

        def ingest_capture(notes):
            nonlocal transferred_note
            transferred_note = notes[0]
            return True

        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.side_effect = ingest_capture

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            ["large-note-test"]
        )

        assert count == 1
        assert transferred_note is not None
        assert len(transferred_note["body"]) == len(large_note["body"])
        assert transferred_note["frontmatter"]["large"] is True
        assert transferred_note["frontmatter"]["word_count"] == 15000


class TestPerformanceAndScalability:
    """Test performance characteristics and scalability."""

    def test_large_batch_performance(self, trojanhorse_client, atlas_mock_client):
        """Test performance with large batches of notes."""
        # Create a large batch of notes
        large_batch = []
        for i in range(50):  # 50 notes
            note = {
                "id": f"perf-note-{i:03d}",
                "path": f"/test/perf-note-{i:03d}.md",
                "title": f"Performance Test Note {i}",
                "body": f"# Performance Test Note {i}\n\nThis is note number {i} for performance testing.",
                "category": "test",
                "project": "performance",
                "tags": [f"perf-{i}", "test"],
                "frontmatter": {"index": i, "batch_size": 50}
            }
            large_batch.append(note)

        # Mock TrojanHorse promotion (simplified)
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                # Measure promotion time
                import time
                start_time = time.time()

                promote_response = trojanhorse_client.post(
                    "/promote",
                    json={"note_ids": [note["id"] for note in large_batch]}
                )

                promotion_time = time.time() - start_time

        assert promote_response.status_code == 200
        assert promotion_time < 5.0  # Should complete within 5 seconds

        # Mock Atlas ingestion
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = True

        # Measure ingestion time
        start_time = time.time()

        count = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            atlas_mock_client,
            [note["id"] for note in large_batch]
        )

        ingestion_time = time.time() - start_time

        assert count == 50
        assert ingestion_time < 2.0  # Should complete within 2 seconds

    def test_concurrent_requests_stress(self, trojanhorse_client, atlas_mock_client):
        """Test system behavior under concurrent request stress."""
        import threading
        import time

        # Setup mocks
        atlas_mock_client.health_check.return_value = True
        atlas_mock_client.ingest_notes.return_value = True

        # Mock TrojanHorse promotion
        with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
            mock_parse.return_value = {
                "meta": {"id": "test", "title": "Test"},
                "body": "# Test\nContent"
            }

            with patch('TrojanHorse.api_server.app.state.index_db.get_file_by_id') as mock_get_file:
                mock_get_file.return_value = {
                    "id": "test",
                    "dest_path": "/test/processed/test.md"
                }

                results = []
                errors = []

                def stress_test(thread_id):
                    try:
                        for i in range(10):  # Each thread makes 10 requests
                        note_ids = [f"stress-{thread_id}-{i}" for i in range(3)]

                        promote_response = trojanhorse_client.post(
                            "/promote",
                            json={"note_ids": note_ids}
                        )

                        count = promote_notes_from_trojanhorse(
                            "http://localhost:8765",
                            atlas_mock_client,
                            note_ids
                        )
                        results.append((thread_id, i, count))
                    except Exception as e:
                        errors.append((thread_id, str(e)))

                # Create stress threads
                threads = []
                start_time = time.time()

                for thread_id in range(5):  # 5 concurrent threads
                    thread = threading.Thread(target=stress_test, args=(thread_id,))
                    threads.append(thread)
                    thread.start()

                # Wait for completion
                for thread in threads:
                    thread.join()

                total_time = time.time() - start_time

                assert len(results) == 50  # 5 threads × 10 requests each
                assert len(errors) == 0  # No errors
                assert total_time < 10.0  # Should complete within 10 seconds

                # Verify Atlas was called correctly
                assert atlas_mock_client.health_check.call_count >= 5
                assert atlas_mock_client.ingest_notes.call_count >= 5