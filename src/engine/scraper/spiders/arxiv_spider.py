"""
arXiv Spider
============
Fetches the latest research papers from the arXiv Atom API (no API key required).
API endpoint: http://export.arxiv.org/api/query

Strategy:
  1. For each configured category, page through the Atom feed in batches.
  2. Optionally follow each paper's abstract page with BeautifulSoup to extract
     the full author list and any "Subjects" breadcrumbs not exposed by the API.
  3. Yield a ResearchPaperItem for every paper published within `days_back` days.
  4. Stop paginating a category once we have walked past the recency window.

Rate-limiting:
  arXiv's usage policy requests ≥ 3 s between requests.
  DOWNLOAD_DELAY = 3.0 and CONCURRENT_REQUESTS = 1 are enforced via custom_settings.

Usage examples:
  # All default categories, last 7 days
  scrapy crawl arxiv

  # Single category, last 30 days, 25 results per page
  scrapy crawl arxiv -a categories=cs.LG -a days_back=30 -a page_size=25

  # Multiple categories (comma-separated)
  scrapy crawl arxiv -a categories=cs.AI,cs.CL,stat.ML -a max_papers=200
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import scrapy
from bs4 import BeautifulSoup

from scraper.items import ResearchPaperItem

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
ARXIV_ABS_BASE = "https://arxiv.org/abs"

# Default AI / ML / CS categories that SYNAPSE tracks
DEFAULT_CATEGORIES = [
    "cs.AI",  # Artificial Intelligence
    "cs.LG",  # Machine Learning
    "cs.CL",  # Computation and Language (NLP)
    "cs.CV",  # Computer Vision and Pattern Recognition
    "cs.NE",  # Neural and Evolutionary Computing
    "cs.SE",  # Software Engineering
    "cs.DC",  # Distributed, Parallel, and Cluster Computing
    "cs.IR",  # Information Retrieval
    "cs.RO",  # Robotics
    "stat.ML",  # Machine Learning (Statistics section)
]

# How many results to request per API call (arXiv max is 2000, but 100 is safe)
DEFAULT_PAGE_SIZE = 100

# Default recency window
DEFAULT_DAYS_BACK = 7

# Default per-category cap (avoids runaway crawls on very active categories)
DEFAULT_MAX_PAPERS = 500


# ── Spider ───────────────────────────────────────────────────────────────────


class ArXivSpider(scrapy.Spider):
    """Scrapy spider for the arXiv Atom API feed."""

    name = "arxiv"
    allowed_domains = ["export.arxiv.org", "arxiv.org"]

    custom_settings = {
        # arXiv explicitly requests ≥ 3 s between automated requests
        "DOWNLOAD_DELAY": 3.0,
        "RANDOMIZE_DOWNLOAD_DELAY": False,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": False,
        # Cache off by default; enable with -s HTTPCACHE_ENABLED=1 during dev
        "HTTPCACHE_ENABLED": False,
    }

    # ── Initialisation ───────────────────────────────────────────────────────

    def __init__(
        self,
        categories=None,
        days_back=DEFAULT_DAYS_BACK,
        page_size=DEFAULT_PAGE_SIZE,
        max_papers=DEFAULT_MAX_PAPERS,
        enrich_abstract_page=False,
        *args,
        **kwargs,
    ):
        """
        Args:
            categories (str): Comma-separated arXiv category codes.
                              Defaults to DEFAULT_CATEGORIES.
            days_back (int):  Only yield papers published in the last N days.
            page_size (int):  Number of results per API request (max 2000).
            max_papers (int): Maximum papers to collect per category.
            enrich_abstract_page (bool | str):
                              If truthy, follow each paper's abstract page on
                              arxiv.org and use BeautifulSoup to scrape extra
                              metadata (full subject list, journal ref, DOI).
                              Adds one extra request per paper — use with care.
        """
        super().__init__(*args, **kwargs)

        self.categories = (
            [c.strip() for c in categories.split(",") if c.strip()]
            if categories
            else DEFAULT_CATEGORIES
        )
        self.days_back = int(days_back)
        self.page_size = min(int(page_size), 2000)  # arXiv hard limit
        self.max_papers = int(max_papers)

        # Accept "True"/"true"/"1" from CLI -a flag as well as Python True
        self.enrich_abstract_page = str(enrich_abstract_page).lower() in (
            "true",
            "1",
            "yes",
        )

        # Store user_id for personalization
        self.user_id = kwargs.get("user_id")

        # Compute the cutoff date once (UTC)
        self.cutoff_date = (
            datetime.now(timezone.utc) - timedelta(days=self.days_back)
        ).date()

        # Track how many papers have been collected per category and globally
        self._category_counts: dict[str, int] = {}
        self._total_count = 0

        logger.info(
            "ArXivSpider initialised | categories=%s | days_back=%d | "
            "page_size=%d | max_papers=%d | enrich=%s | cutoff=%s",
            self.categories,
            self.days_back,
            self.page_size,
            self.max_papers,
            self.enrich_abstract_page,
            self.cutoff_date,
        )

    # ── Entry points ─────────────────────────────────────────────────────────

    def start_requests(self):
        """Generate one initial request per category."""
        for category in self.categories:
            self._category_counts[category] = 0
            yield self._build_api_request(category, start=0)

    # ── API request builder ──────────────────────────────────────────────────

    def _build_api_request(self, category: str, start: int) -> scrapy.Request:
        """Build a paginated arXiv API request for a single category."""
        params = {
            "search_query": f"cat:{category}",
            "start": start,
            "max_results": self.page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_BASE}?{urlencode(params)}"
        return scrapy.Request(
            url,
            callback=self.parse_feed,
            errback=self.handle_error,
            meta={
                "category": category,
                "page_start": start,
            },
            # Don't filter duplicate URLs — different `start` values are distinct
            dont_filter=False,
        )

    # ── Feed parsing ─────────────────────────────────────────────────────────

    def parse_feed(self, response):
        """
        Parse an Atom XML feed page returned by the arXiv API.

        Yields:
            ResearchPaperItem  – one per valid entry within the recency window.
            scrapy.Request     – next page request if more results exist and
                                 we haven't exceeded max_papers or fallen out
                                 of the recency window.
        """
        category = response.meta["category"]
        page_start = response.meta["page_start"]

        # Remove XML namespaces so plain XPath works
        response.selector.remove_namespaces()

        # ── Feed-level metadata ───────────────────────────────────────────
        total_results = int(response.xpath("//feed/totalResults/text()").get("0") or 0)
        entries = response.xpath("//entry")
        fetched = len(entries)

        logger.info(
            "arXiv [%s] page start=%d | feed total=%d | fetched=%d entries",
            category,
            page_start,
            total_results,
            fetched,
        )

        if fetched == 0:
            logger.info("arXiv [%s]: no more entries — stopping.", category)
            return

        # ── Per-entry processing ──────────────────────────────────────────
        reached_cutoff = False

        for entry in entries:
            # Check global cap (max_papers is total across all categories)
            if self._total_count >= self.max_papers:
                logger.info(
                    "arXiv: reached global max_papers=%d (total collected) — stopping.",
                    self.max_papers,
                )
                return

            arxiv_id, published_date, item = self._parse_entry(entry, category)

            if item is None:
                continue  # Parsing failed; already logged

            # ── Recency filter ────────────────────────────────────────────
            if published_date is not None and published_date < self.cutoff_date:
                logger.debug(
                    "arXiv [%s]: paper %s published %s is before cutoff %s — "
                    "stopping pagination for this category.",
                    category,
                    arxiv_id,
                    published_date,
                    self.cutoff_date,
                )
                reached_cutoff = True
                break  # Feed is sorted newest-first; nothing older is relevant

            self._category_counts[category] += 1
            self._total_count += 1

            if self.enrich_abstract_page:
                # Follow the abstract page for richer metadata
                abs_url = f"{ARXIV_ABS_BASE}/{arxiv_id}"
                yield scrapy.Request(
                    abs_url,
                    callback=self.parse_abstract_page,
                    errback=self.handle_error,
                    meta={"item": item},
                    priority=1,  # Slightly lower priority than API calls
                )
            else:
                yield item

        # ── Pagination ────────────────────────────────────────────────────
        if reached_cutoff:
            return  # No point fetching older pages

        next_start = page_start + fetched
        papers_collected = self._category_counts[category]

        if (
            next_start < total_results
            and self._total_count < self.max_papers
            and fetched == self.page_size  # Partial page = last page
        ):
            logger.debug(
                "arXiv [%s]: fetching next page (start=%d, collected=%d).",
                category,
                next_start,
                papers_collected,
            )
            yield self._build_api_request(category, start=next_start)

    # ── Entry parser ─────────────────────────────────────────────────────────

    def _parse_entry(self, entry, category: str):
        """
        Extract a ResearchPaperItem from a single Atom <entry> element.

        Returns:
            Tuple[str, date | None, ResearchPaperItem | None]
            On failure returns (arxiv_id or '', None, None).
        """
        raw_id_url = entry.xpath("id/text()").get("").strip()
        arxiv_id = self._extract_arxiv_id(raw_id_url)

        if not arxiv_id:
            logger.warning("arXiv: could not extract arxiv_id from %r", raw_id_url)
            return "", None, None

        # ── Title ─────────────────────────────────────────────────────────
        title = self._clean_whitespace(entry.xpath("title/text()").get("").strip())

        # ── Abstract ─────────────────────────────────────────────────────
        abstract = self._clean_whitespace(entry.xpath("summary/text()").get("").strip())

        # ── Authors ───────────────────────────────────────────────────────
        authors = entry.xpath("author/name/text()").getall()

        # ── Categories ────────────────────────────────────────────────────
        categories = entry.xpath("category/@term").getall()

        # ── Published date ────────────────────────────────────────────────
        published_str = entry.xpath("published/text()").get("")
        published_date = self._parse_iso_date(published_str)

        # ── Updated date ──────────────────────────────────────────────────
        updated_str = entry.xpath("updated/text()").get("")

        # ── PDF link ──────────────────────────────────────────────────────
        pdf_url = ""
        for link in entry.xpath("link"):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "").strip()
                # Ensure HTTPS
                if pdf_url.startswith("http://"):
                    pdf_url = "https://" + pdf_url[7:]
                break

        # ── Canonical abstract URL ────────────────────────────────────────
        abs_url = raw_id_url.strip()
        # Normalise to HTTPS
        if abs_url.startswith("http://"):
            abs_url = "https://" + abs_url[7:]

        # ── Additional metadata ───────────────────────────────────────────
        journal_ref = entry.xpath("journal_ref/text()").get("") or ""
        doi = entry.xpath("doi/text()").get("") or ""
        comment = entry.xpath("comment/text()").get("") or ""

        item = ResearchPaperItem(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            authors=authors,
            categories=categories,
            published_date=published_date.isoformat() if published_date else None,
            url=abs_url,
            pdf_url=pdf_url,
            metadata={
                "updated": updated_str,
                "comment": self._clean_whitespace(comment),
                "journal_ref": journal_ref,
                "doi": doi,
                "source_category": category,
                "version": self._extract_version(raw_id_url),
            },
        )

        return arxiv_id, published_date, item

    # ── Abstract page enrichment (optional) ──────────────────────────────────

    def parse_abstract_page(self, response):
        """
        Optionally enrich a ResearchPaperItem by scraping the arXiv abstract
        HTML page with BeautifulSoup.

        Extra fields extracted:
          - Full subject / category labels (human-readable)
          - Journal reference (if published)
          - DOI link
          - MSC / ACM classification codes (when present)

        Yields:
            ResearchPaperItem with enriched metadata.
        """
        item = response.meta["item"]

        try:
            soup = BeautifulSoup(response.text, "lxml")

            # ── Subject labels ────────────────────────────────────────────
            subject_spans = soup.select("span.primary-subject, td.subjects span")
            subject_labels = [
                s.get_text(strip=True) for s in subject_spans if s.get_text(strip=True)
            ]

            # ── Journal reference ─────────────────────────────────────────
            journal_td = soup.find("td", class_="tablecell jref")
            if journal_td:
                item["metadata"]["journal_ref"] = journal_td.get_text(strip=True)

            # ── DOI ───────────────────────────────────────────────────────
            doi_td = soup.find("td", class_="tablecell doi")
            if doi_td:
                doi_link = doi_td.find("a")
                if doi_link:
                    item["metadata"]["doi"] = doi_link.get("href", "").strip()

            # ── MSC / ACM codes ───────────────────────────────────────────
            msc_td = soup.find("td", class_="tablecell msc-classes")
            if msc_td:
                item["metadata"]["msc_classes"] = msc_td.get_text(strip=True)

            acm_td = soup.find("td", class_="tablecell acm-classes")
            if acm_td:
                item["metadata"]["acm_classes"] = acm_td.get_text(strip=True)

            if subject_labels:
                item["metadata"]["subject_labels"] = subject_labels

            logger.debug(
                "arXiv abstract page enriched: %s | subjects=%s",
                item.get("arxiv_id"),
                subject_labels,
            )

        except Exception as exc:
            logger.warning(
                "arXiv: failed to parse abstract page %s — %s",
                response.url,
                exc,
            )

        yield item

    # ── Error handler ─────────────────────────────────────────────────────────

    def handle_error(self, failure):
        """Log download/network errors without crashing the crawl."""
        logger.error(
            "arXiv spider request failed | url=%s | error=%s",
            failure.request.url,
            failure.value,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_arxiv_id(url: str) -> str:
        """
        Extract the bare arXiv ID from an abstract URL.

        Examples:
            http://arxiv.org/abs/2401.12345v1  ->  2401.12345
            https://arxiv.org/abs/cs/0612058v2 ->  cs/0612058
        """
        if "/abs/" in url:
            raw = url.split("/abs/")[-1].strip()
            # Strip version suffix (v1, v2, …) — keep the stable ID
            return re.sub(r"v\d+$", "", raw)
        return url.strip()

    @staticmethod
    def _extract_version(url: str) -> str:
        """Return the version string (e.g. 'v2') from an arXiv URL, or ''."""
        match = re.search(r"v(\d+)$", url.strip())
        return f"v{match.group(1)}" if match else ""

    @staticmethod
    def _parse_iso_date(date_str: str):
        """
        Parse an ISO 8601 datetime string returned by the arXiv API into a
        Python date object (UTC).  Returns None on failure.

        arXiv format: '2024-01-15T18:00:00Z'
        """
        if not date_str:
            return None
        try:
            # Python 3.7+: fromisoformat doesn't handle trailing 'Z'
            return (
                datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                .astimezone(timezone.utc)
                .date()
            )
        except (ValueError, TypeError):
            # Fall back: just take the first 10 chars (YYYY-MM-DD)
            try:
                return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                logger.warning("arXiv: could not parse date %r", date_str)
                return None

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """Collapse internal whitespace / newlines (common in arXiv abstracts)."""
        return re.sub(r"\s+", " ", text).strip()
