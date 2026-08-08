from __future__ import annotations

import os
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download/cache the summarization model (facebook/bart-large-cnn) by initializing the pipeline once."

    def handle(self, *args, **options):
        # Ensure ai_engine is importable
        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                )
            )
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        self.stdout.write(
            self.style.NOTICE(
                "Initializing summarizer (this may take a few minutes)..."
            )
        )
        try:
            import ai_engine.nlp.summarizer as summ

            # Allow override via env var if desired
            os.environ.setdefault("SUMMARIZER_MODEL", summ.DEFAULT_MODEL)
            # Initialize once to trigger download/cache
            pipe = summ._get_summarizer()
            if pipe is None:
                self.stderr.write(
                    self.style.ERROR("Failed to initialize summarizer pipeline.")
                )
                return
            self.stdout.write(self.style.SUCCESS("Summarizer ready and cached."))
            return
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Warmup failed: {exc}"))
            return
