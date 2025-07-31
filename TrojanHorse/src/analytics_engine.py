#!/usr/bin/env python3
"""
Analytics Engine for TrojanHorse Context Capture System
"""

import spacy
import sqlite3
from pathlib import Path
import logging
from datetime import datetime, timedelta

class AnalyticsEngine:
    def __init__(self, db_path="trojan_search.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self.nlp = spacy.load("en_core_web_sm")
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def run_full_analysis(self):
        """Run full analysis on all transcripts that have not been analyzed."""
        self.logger.info("Starting full analysis...")
        cursor = self.conn.execute("SELECT id, content FROM transcripts WHERE id NOT IN (SELECT DISTINCT transcript_id FROM analytics_entities)")
        transcripts = cursor.fetchall()
        self.logger.info(f"Found {len(transcripts)} new transcripts to analyze.")

        for transcript in transcripts:
            self.logger.info(f"Analyzing transcript {transcript['id']}...")
            doc = self.nlp(transcript['content'])
            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG", "GPE"]:
                    self.conn.execute("INSERT INTO analytics_entities (transcript_id, entity_text, entity_type, timestamp) VALUES (?, ?, ?, ?)",
                                      (transcript['id'], ent.text, ent.label_, datetime.now()))
            self.conn.commit()
        self.logger.info("Full analysis complete.")

    def calculate_trends(self):
        """Calculate trends for entities."""
        self.logger.info("Calculating trends...")
        self.conn.execute("DELETE FROM analytics_trends")

        end_date = datetime.now()
        mid_date = end_date - timedelta(days=7)
        start_date = mid_date - timedelta(days=7)

        query = """
        SELECT entity_text, COUNT(*) as count
        FROM analytics_entities
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY entity_text
        """

        old_cursor = self.conn.execute(query, (start_date, mid_date))
        old_counts = {row['entity_text']: row['count'] for row in old_cursor.fetchall()}

        new_cursor = self.conn.execute(query, (mid_date, end_date))
        new_counts = {row['entity_text']: row['count'] for row in new_cursor.fetchall()}

        trends = []
        for entity, new_count in new_counts.items():
            old_count = old_counts.get(entity, 0)
            if old_count > 0:
                score = (new_count - old_count) / old_count
            else:
                score = new_count
            trends.append((entity, score))

        trends.sort(key=lambda x: x[1], reverse=True)

        for entity, score in trends[:5]:
            self.conn.execute("INSERT INTO analytics_trends (entity_text, trend_score, last_updated) VALUES (?, ?, ?)",
                              (entity, score, datetime.now()))
        self.conn.commit()
        self.logger.info("Trend calculation complete.")

    def close(self):
        if self.conn:
            self.conn.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    engine = AnalyticsEngine()
    engine.run_full_analysis()
    engine.calculate_trends()
    engine.close()
