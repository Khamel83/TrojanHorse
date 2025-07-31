#!/usr/bin/env python3
"""
Web Interface for TrojanHorse Context Capture System
Phase 3: Web Interface - Flask-based search and timeline interface
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

from search_engine import SearchEngine
from semantic_search import SemanticSearch

class TrojanWebInterface:
    """Flask web interface for TrojanHorse search and analysis"""
    
    def __init__(self, db_path: str = "trojan_search.db", 
                 host: str = "127.0.0.1", port: int = 5000):
        self.db_path = db_path
        self.host = host
        self.port = port
        self.logger = logging.getLogger(__name__)
        
        # Initialize search engines
        self.search_engine = SearchEngine(db_path)
        self.semantic_search = SemanticSearch(db_path)
        
        # Initialize Flask app
        self.app = Flask(__name__, 
                        template_folder='../templates',
                        static_folder='../static')
        CORS(self.app)
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main search interface"""
            stats = self.search_engine.get_stats()
            return render_template('index.html', stats=stats)
        
        @self.app.route('/api/search', methods=['POST'])
        def api_search():
            """API endpoint for search"""
            try:
                data = request.get_json()
                query = data.get('query', '').strip()
                search_type = data.get('type', 'hybrid')  # keyword, semantic, hybrid
                limit = min(int(data.get('limit', 20)), 100)
                date_from = data.get('date_from')
                date_to = data.get('date_to')
                classification = data.get('classification')
                
                if not query:
                    return jsonify({'error': 'Query is required'}), 400
                
                # Perform search based on type
                if search_type == 'keyword':
                    results = self._keyword_search(query, limit, date_from, date_to, classification)
                elif search_type == 'semantic':
                    results = self._semantic_search(query, limit, date_from, date_to)
                elif search_type == 'hybrid':
                    results = self._hybrid_search(query, limit, date_from, date_to)
                else:
                    return jsonify({'error': 'Invalid search type'}), 400
                
                return jsonify({
                    'query': query,
                    'type': search_type,
                    'count': len(results),
                    'results': results
                })
                
            except Exception as e:
                self.logger.error(f"Search API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/stats')
        def api_stats():
            """API endpoint for database statistics"""
            try:
                search_stats = self.search_engine.get_stats()
                embedding_stats = self.semantic_search.get_embedding_stats()
                
                return jsonify({
                    'search': search_stats,
                    'embeddings': embedding_stats
                })
                
            except Exception as e:
                self.logger.error(f"Stats API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/timeline')
        def api_timeline():
            """API endpoint for timeline analysis"""
            try:
                days = int(request.args.get('days', 30))
                
                # Get timeline data from database
                timeline_data = self._get_timeline_data(days)
                
                return jsonify(timeline_data)
                
            except Exception as e:
                self.logger.error(f"Timeline API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/export', methods=['POST'])
        def api_export():
            """API endpoint for exporting search results"""
            try:
                data = request.get_json()
                results = data.get('results', [])
                format_type = data.get('format', 'json')  # json, csv, md
                
                if format_type == 'json':
                    return jsonify(results)
                elif format_type == 'csv':
                    csv_data = self._export_csv(results)
                    return csv_data, 200, {
                        'Content-Type': 'text/csv',
                        'Content-Disposition': 'attachment; filename=search_results.csv'
                    }
                elif format_type == 'md':
                    md_data = self._export_markdown(results)
                    return md_data, 200, {
                        'Content-Type': 'text/markdown',
                        'Content-Disposition': 'attachment; filename=search_results.md'
                    }
                else:
                    return jsonify({'error': 'Invalid format type'}), 400
                    
            except Exception as e:
                self.logger.error(f"Export API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/transcript/<int:transcript_id>')
        def view_transcript(transcript_id):
            """View full transcript"""
            try:
                # Get transcript from database
                cursor = self.search_engine.conn.execute("""
                    SELECT t.*, a.summary, a.action_items, a.tags, a.classification
                    FROM transcripts t
                    LEFT JOIN analysis a ON t.id = a.transcript_id
                    WHERE t.id = ?
                """, (transcript_id,))
                
                transcript = cursor.fetchone()
                if not transcript:
                    return "Transcript not found", 404
                
                # Parse JSON fields
                action_items = json.loads(transcript['action_items']) if transcript['action_items'] else []
                tags = json.loads(transcript['tags']) if transcript['tags'] else []
                
                return render_template('transcript.html', 
                                     transcript=transcript,
                                     action_items=action_items,
                                     tags=tags)
                
            except Exception as e:
                self.logger.error(f"Transcript view error: {e}")
                return f"Error: {e}", 500
    
    def _keyword_search(self, query: str, limit: int, date_from: Optional[str], 
                       date_to: Optional[str], classification: Optional[str]) -> List[Dict]:
        """Perform keyword search"""
        results = self.search_engine.search(
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            classification=classification
        )
        
        return [self._format_search_result(r, 'keyword') for r in results]
    
    def _semantic_search(self, query: str, limit: int, date_from: Optional[str], 
                        date_to: Optional[str]) -> List[Dict]:
        """Perform semantic search"""
        results = self.semantic_search.semantic_search(
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to
        )
        
        return [self._format_semantic_result(r, 'semantic') for r in results]
    
    def _hybrid_search(self, query: str, limit: int, date_from: Optional[str], 
                      date_to: Optional[str]) -> List[Dict]:
        """Perform hybrid search"""
        results = self.semantic_search.hybrid_search(
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to
        )
        
        return [self._format_hybrid_result(r) for r in results]
    
    def _format_search_result(self, result, search_type: str) -> Dict:
        """Format search result for API response"""
        return {
            'transcript_id': result.transcript_id,
            'filename': result.filename,
            'date': result.date,
            'timestamp': result.timestamp,
            'snippet': result.snippet,
            'score': result.score,
            'search_type': search_type,
            'analysis_summary': result.analysis_summary,
            'action_items': result.action_items,
            'tags': result.tags
        }
    
    def _format_semantic_result(self, result, search_type: str) -> Dict:
        """Format semantic search result for API response"""
        return {
            'transcript_id': result.transcript_id,
            'filename': result.filename,
            'date': result.date,
            'timestamp': result.timestamp,
            'snippet': result.snippet,
            'similarity': result.similarity,
            'search_type': search_type,
            'analysis_summary': result.analysis_summary,
            'action_items': result.action_items,
            'tags': result.tags
        }
    
    def _format_hybrid_result(self, result) -> Dict:
        """Format hybrid search result for API response"""
        return {
            'transcript_id': result['transcript_id'],
            'filename': result['filename'],
            'date': result['date'],
            'timestamp': result['timestamp'],
            'snippet': result['snippet'],
            'combined_score': result['combined_score'],
            'keyword_score': result['keyword_score'],
            'semantic_score': result['semantic_score'],
            'search_type': result['source'],
            'analysis_summary': result['analysis_summary'],
            'action_items': result['action_items'],
            'tags': result['tags']
        }
    
    def _get_timeline_data(self, days: int) -> Dict:
        """Get timeline analysis data"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        cursor = self.search_engine.conn.execute("""
            SELECT 
                DATE(t.date) as date,
                COUNT(*) as transcript_count,
                SUM(t.word_count) as total_words,
                GROUP_CONCAT(DISTINCT a.classification) as classifications
            FROM transcripts t
            LEFT JOIN analysis a ON t.id = a.transcript_id
            WHERE t.date >= ? AND t.date <= ?
            GROUP BY DATE(t.date)
            ORDER BY date
        """, (start_date.isoformat(), end_date.isoformat()))
        
        timeline_data = []
        for row in cursor.fetchall():
            classifications = row['classifications'].split(',') if row['classifications'] else []
            timeline_data.append({
                'date': row['date'],
                'transcript_count': row['transcript_count'],
                'total_words': row['total_words'] or 0,
                'classifications': [c.strip() for c in classifications if c.strip()]
            })
        
        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
            'timeline': timeline_data
        }
    
    def _export_csv(self, results: List[Dict]) -> str:
        """Export results as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        if not results:
            return ""
        
        fieldnames = ['transcript_id', 'filename', 'date', 'timestamp', 'snippet', 
                     'score', 'search_type', 'analysis_summary']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            row = {k: v for k, v in result.items() if k in fieldnames}
            writer.writerow(row)
        
        return output.getvalue()
    
    def _export_markdown(self, results: List[Dict]) -> str:
        """Export results as Markdown"""
        if not results:
            return "# Search Results\n\nNo results found."
        
        md_content = "# Search Results\n\n"
        
        for i, result in enumerate(results, 1):
            md_content += f"## {i}. {result['filename']}\n\n"
            md_content += f"**Date:** {result['date']}  \n"
            md_content += f"**Score:** {result.get('score', result.get('combined_score', 'N/A'))}  \n"
            md_content += f"**Type:** {result['search_type']}  \n\n"
            
            if result.get('analysis_summary'):
                md_content += f"**Summary:** {result['analysis_summary']}  \n\n"
            
            md_content += f"**Snippet:**  \n{result['snippet']}\n\n"
            
            if result.get('action_items'):
                md_content += "**Action Items:**  \n"
                for item in result['action_items']:
                    md_content += f"- {item}\n"
                md_content += "\n"
            
            if result.get('tags'):
                md_content += f"**Tags:** {', '.join(result['tags'])}\n\n"
            
            md_content += "---\n\n"
        
        return md_content
    
    def run(self, debug: bool = False):
        """Run the Flask application"""
        self.logger.info(f"Starting TrojanHorse web interface on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug)
    
    def close(self):
        """Close database connections"""
        self.search_engine.close()
        self.semantic_search.close()

def main():
    """Run the web interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TrojanHorse Web Interface')
    parser.add_argument('--database', '-d', default='trojan_search.db',
                       help='SQLite database path')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Host to bind to')
    parser.add_argument('--port', '-p', type=int, default=5000,
                       help='Port to bind to')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run web interface
    web_interface = TrojanWebInterface(
        db_path=args.database,
        host=args.host,
        port=args.port
    )
    
    try:
        web_interface.run(debug=args.debug)
    except KeyboardInterrupt:
        logging.info("Shutting down web interface...")
    finally:
        web_interface.close()

if __name__ == "__main__":
    main()