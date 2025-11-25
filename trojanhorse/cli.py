"""CLI interface for TrojanHorse."""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from .config import Config
from .processor import Processor
from .rag import rebuild_index, query
from .index_db import IndexDB
from .llm_client import LLMClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# Create CLI app
app = typer.Typer(
    help="TrojanHorse: Local Vault Processor + Q&A",
    no_args_is_help=True
)


def load_config() -> Config:
    """Load configuration and handle errors gracefully."""
    try:
        return Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        typer.echo("Please check your .env file and ensure all required variables are set.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Unexpected configuration error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def setup() -> None:
    """Set up TrojanHorse environment."""
    typer.echo("🔧 Setting up TrojanHorse...")

    try:
        config = load_config()

        # Validate configuration
        config.validate()

        # Ensure directories exist
        config.ensure_directories()

        # Initialize databases
        index_db = IndexDB(config.state_dir)

        # Test LLM connection if API key is provided
        if config.openrouter_api_key:
            typer.echo("🔗 Testing OpenRouter connection...")
            llm_client = LLMClient(config.openrouter_api_key, config.openrouter_model)
            if llm_client.test_connection():
                typer.echo("✅ OpenRouter connection successful")
            else:
                typer.echo("⚠️  OpenRouter connection failed - check your API key")
        else:
            typer.echo("⚠️  No OpenRouter API key configured")

        # Get stats
        index_stats = index_db.get_stats()
        typer.echo(f"📊 Processed files database: {index_stats['total_files']} files")
        typer.echo(f"📁 State directory: {config.state_dir}")
        typer.echo(f"📁 Vault root: {config.vault_root}")
        typer.echo(f"📁 Capture directories: {[d.name for d in config.capture_dirs]}")

        typer.echo("✅ TrojanHorse setup complete!")
        typer.echo("\nNext steps:")
        typer.echo("  • Add files to your capture directories")
        typer.echo("  • Run 'th process' to process them")
        typer.echo("  • Run 'th workday' for continuous processing")
        typer.echo("  • Run 'th embed' to build the search index")
        typer.echo("  • Use 'th ask \"your question\"' to query your notes")

    except Exception as e:
        typer.echo(f"❌ Setup failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def process() -> None:
    """Process new files once and exit (cron-friendly)."""
    typer.echo("🔄 Processing new files...")

    try:
        config = load_config()
        processor = Processor(config)

        # Run one processing cycle
        stats = processor.process_once()

        # Report results
        typer.echo(f"✅ Processing complete in {stats.duration_seconds:.1f}s")
        typer.echo(f"📄 Files scanned: {stats.files_scanned}")
        typer.echo(f"✅ Files processed: {stats.files_processed}")
        typer.echo(f"⏭️  Files skipped: {stats.files_skipped}")

        if stats.errors:
            typer.echo(f"⚠️  Errors encountered: {len(stats.errors)}")
            for error in stats.errors[:3]:  # Show first 3 errors
                typer.echo(f"   • {error}")
            if len(stats.errors) > 3:
                typer.echo(f"   ... and {len(stats.errors) - 3} more")

    except Exception as e:
        typer.echo(f"❌ Processing failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def workday(
    interval: int = typer.Option(300, "--interval", "-i", help="Seconds between processing cycles")
) -> None:
    """Run processing loop for a workday session."""
    typer.echo(f"🏃 Starting workday loop (every {interval}s)")
    typer.echo("Press Ctrl+C to stop")

    try:
        config = load_config()
        processor = Processor(config)

        # Run the workday loop
        processor.workday_loop(interval_seconds=interval)

    except KeyboardInterrupt:
        typer.echo("\n👋 Workday loop stopped")
    except Exception as e:
        typer.echo(f"❌ Workday loop failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def embed() -> None:
    """Rebuild the RAG embedding index."""
    typer.echo("🔍 Rebuilding RAG index...")

    try:
        config = load_config()
        rebuild_index(config)

        typer.echo("✅ RAG index rebuild complete!")

    except Exception as e:
        typer.echo(f"❌ RAG index rebuild failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask your notes"),
    top_k: int = typer.Option(8, "--top-k", "-k", help="Number of context notes to retrieve")
) -> None:
    """Ask a question and get answers from your notes."""
    try:
        config = load_config()

        typer.echo(f"🤔 Asking: {question}")

        # Query the RAG system
        result = query(config, question, k=top_k)

        # Display answer
        typer.echo(f"\n💬 Answer:")
        typer.echo(result["answer"])

        # Display context sources
        if result["contexts"]:
            typer.echo(f"\n📚 Sources:")
            for i, context in enumerate(result["contexts"], 1):
                path = Path(context["path"])
                relative_path = path.relative_to(config.vault_root) if path.is_relative_to(config.vault_root) else path.name
                typer.echo(f"  {i}. {relative_path} (similarity: {context['similarity']:.2f})")

        else:
            typer.echo("\n📚 No relevant sources found")

    except Exception as e:
        typer.echo(f"❌ Query failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show TrojanHorse system status."""
    try:
        config = load_config()

        typer.echo("📊 TrojanHorse Status")
        typer.echo("=" * 40)

        # Configuration info
        typer.echo(f"📁 Vault root: {config.vault_root}")
        typer.echo(f"📂 Capture directories: {[d.name for d in config.capture_dirs]}")
        if config.processed_root:
            typer.echo(f"📂 Processed directory: {config.processed_root.name}")
        typer.echo(f"💾 State directory: {config.state_dir}")
        typer.echo(f"🤖 LLM model: {config.openrouter_model}")

        # Processed files database stats
        index_db = IndexDB(config.state_dir)
        index_stats = index_db.get_stats()
        typer.echo(f"\n📄 Processed files: {index_stats['total_files']}")
        if index_stats['total_size_bytes'] > 0:
            size_mb = index_stats['total_size_bytes'] / (1024 * 1024)
            typer.echo(f"💾 Total size: {size_mb:.1f} MB")

        # RAG index stats
        from .rag import RAGIndex
        rag_index = RAGIndex(config.state_dir, config)
        rag_stats = rag_index.get_stats()
        typer.echo(f"🔍 Indexed notes: {rag_stats['total_notes']}")
        if rag_stats['categories']:
            typer.echo("📂 Categories:")
            for category, count in rag_stats['categories'].items():
                typer.echo(f"   • {category}: {count}")

        # Test connections
        typer.echo(f"\n🔗 Connections:")
        if config.openrouter_api_key:
            typer.echo("   ✅ OpenRouter API key configured")
        else:
            typer.echo("   ❌ No OpenRouter API key")

        if config.embedding_api_key:
            typer.echo("   ✅ Embedding API key configured")
        else:
            typer.echo("   ⚠️  No embedding API key (using fallback)")

    except Exception as e:
        typer.echo(f"❌ Status check failed: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Main CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()