__package__ = 'archivebox.index'

import archivebox
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional, Iterator, Mapping

from django.utils.html import format_html, mark_safe   # type: ignore
from django.core.cache import cache

from .schema import Link
from ..system import atomic_write
from ..logging_util import printable_filesize
from ..util import (
    enforce_types,
    ts_to_date_str,
    urlencode,
    htmlencode,
    urldecode,
)
from ..config import (
    SAVE_ARCHIVE_DOT_ORG,
    PREVIEW_ORIGINALS,
)

MAIN_INDEX_TEMPLATE = 'static_index.html'
MINIMAL_INDEX_TEMPLATE = 'minimal_index.html'
LINK_DETAILS_TEMPLATE = 'snapshot.html'
TITLE_LOADING_MSG = 'Not yet archived...'


### Main Links Index

@enforce_types
def parse_html_main_index(out_dir: Path=archivebox.DATA_DIR) -> Iterator[str]:
    """parse an archive index html file and return the list of urls"""

    from plugins_sys.config.constants import CONSTANTS

    index_path = Path(out_dir) / CONSTANTS.HTML_INDEX_FILENAME
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            for line in f:
                if 'class="link-url"' in line:
                    yield line.split('"')[1]
    return ()

@enforce_types
def generate_index_from_links(links: List[Link], with_headers: bool):
    if with_headers:
        output = main_index_template(links)
    else:
        output = main_index_template(links, template=MINIMAL_INDEX_TEMPLATE)
    return output

@enforce_types
def main_index_template(links: List[Link], template: str=MAIN_INDEX_TEMPLATE) -> str:
    """render the template for the entire main index"""

    from plugins_sys.config.apps import SHELL_CONFIG, SERVER_CONFIG

    return render_django_template(template, {
        'version': archivebox.VERSION,
        'git_sha': SHELL_CONFIG.COMMIT_HASH or archivebox.VERSION,
        'num_links': str(len(links)),
        'date_updated': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'time_updated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
        'links': [link._asdict(extended=True) for link in links],
        'FOOTER_INFO': SERVER_CONFIG.FOOTER_INFO,
    })


### Link Details Index

@enforce_types
def write_html_link_details(link: Link, out_dir: Optional[str]=None) -> None:
    from plugins_sys.config.constants import CONSTANTS
    out_dir = out_dir or link.link_dir

    rendered_html = link_details_template(link)
    atomic_write(str(Path(out_dir) / CONSTANTS.HTML_INDEX_FILENAME), rendered_html)


@enforce_types
def link_details_template(link: Link) -> str:

    from ..extractors.wget import wget_output_path

    link_info = link._asdict(extended=True)

    return render_django_template(LINK_DETAILS_TEMPLATE, {
        **link_info,
        **link_info['canonical'],
        'title': htmlencode(
            link.title
            or (link.base_url if link.is_archived else TITLE_LOADING_MSG)
        ),
        'url_str': htmlencode(urldecode(link.base_url)),
        'archive_url': urlencode(
            wget_output_path(link)
            or (link.domain if link.is_archived else '')
        ) or 'about:blank',
        'extension': link.extension or 'html',
        'tags': link.tags or 'untagged',
        'size': printable_filesize(link.archive_size) if link.archive_size else 'pending',
        'status': 'archived' if link.is_archived else 'not yet archived',
        'status_color': 'success' if link.is_archived else 'danger',
        'oldest_archive_date': ts_to_date_str(link.oldest_archive_date),
        'SAVE_ARCHIVE_DOT_ORG': SAVE_ARCHIVE_DOT_ORG,
        'PREVIEW_ORIGINALS': PREVIEW_ORIGINALS,
    })

@enforce_types
def render_django_template(template: str, context: Mapping[str, str]) -> str:
    """render a given html template string with the given template content"""
    from django.template.loader import render_to_string

    return render_to_string(template, context)


def snapshot_icons(snapshot) -> str:
    cache_key = f'result_icons:{snapshot.pk}:{(snapshot.downloaded_at or snapshot.modified_at or snapshot.created_at or snapshot.bookmarked_at).timestamp()}'
    
    def calc_snapshot_icons():
        from core.models import ArchiveResult
        # start = datetime.now(timezone.utc)

        if hasattr(snapshot, '_prefetched_objects_cache') and 'archiveresult_set' in snapshot._prefetched_objects_cache:
            archive_results = [
                result
                for result in snapshot.archiveresult_set.all()
                if result.status == "succeeded" and result.output
            ]
        else:
            archive_results = snapshot.archiveresult_set.filter(status="succeeded", output__isnull=False)

        # import ipdb; ipdb.set_trace()
        link = snapshot.as_link()
        path = link.archive_path
        canon = link.canonical_outputs()
        output = ""
        output_template = '<a href="/{}/{}" class="exists-{}" title="{}">{}</a> &nbsp;'
        icons = {
            "singlefile": "❶",
            "wget": "🆆",
            "dom": "🅷",
            "pdf": "📄",
            "screenshot": "💻",
            "media": "📼",
            "git": "🅶",
            "archive_org": "🏛",
            "readability": "🆁",
            "mercury": "🅼",
            "warc": "📦"
        }
        exclude = ["favicon", "title", "headers", "htmltotext", "archive_org"]
        # Missing specific entry for WARC

        extractor_outputs = defaultdict(lambda: None)
        for extractor, _ in ArchiveResult.EXTRACTOR_CHOICES:
            for result in archive_results:
                if result.extractor == extractor and result:
                    extractor_outputs[extractor] = result

        for extractor, _ in ArchiveResult.EXTRACTOR_CHOICES:
            if extractor not in exclude:
                existing = extractor_outputs[extractor] and extractor_outputs[extractor].status == 'succeeded' and extractor_outputs[extractor].output
                # Check filesystsem to see if anything is actually present (too slow, needs optimization/caching)
                # if existing:
                #     existing = (Path(path) / existing)
                #     if existing.is_file():
                #         existing = True
                #     elif existing.is_dir():
                #         existing = any(existing.glob('*.*'))
                output += format_html(output_template, path, canon[f"{extractor}_path"], str(bool(existing)),
                                             extractor, icons.get(extractor, "?"))
            if extractor == "wget":
                # warc isn't technically it's own extractor, so we have to add it after wget
                
                # get from db (faster but less thurthful)
                exists = extractor_outputs[extractor] and extractor_outputs[extractor].status == 'succeeded' and extractor_outputs[extractor].output
                # get from filesystem (slower but more accurate)
                # exists = list((Path(path) / canon["warc_path"]).glob("*.warc.gz"))
                output += format_html(output_template, path, canon["warc_path"], str(bool(exists)), "warc", icons.get("warc", "?"))

            if extractor == "archive_org":
                # The check for archive_org is different, so it has to be handled separately

                # get from db (faster)
                exists = extractor in extractor_outputs and extractor_outputs[extractor] and extractor_outputs[extractor].status == 'succeeded' and extractor_outputs[extractor].output
                # get from filesystem (slower)
                # target_path = Path(path) / "archive.org.txt"
                # exists = target_path.exists()
                output += '<a href="{}" class="exists-{}" title="{}">{}</a> '.format(canon["archive_org_path"], str(exists),
                                                                                            "archive_org", icons.get("archive_org", "?"))

        result = format_html('<span class="files-icons" style="font-size: 1.1em; opacity: 0.8; min-width: 240px; display: inline-block">{}<span>', mark_safe(output))
        # end = datetime.now(timezone.utc)
        # print(((end - start).total_seconds()*1000) // 1, 'ms')
        return result

    cache_result = cache.get(cache_key)
    if cache_result:
        return cache_result
    
    fresh_result = calc_snapshot_icons()
    cache.set(cache_key, fresh_result, timeout=60 * 60 * 24)
    return fresh_result

   
