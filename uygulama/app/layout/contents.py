"""Printed table-of-contents recognition before destructive layout filters."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from statistics import median

from app.core.models import BoundingBox, ParsedPage, PrintedTocEntry, SourceTextBlock
from app.core.normalizer import normalize_text
from app.layout.columns import ReadingOrderResolver

_CONTENTS_HEADINGS = {
    "contents",
    "tableofcontents",
    "icindekiler",
    "sommaire",
    "inhaltsverzeichnis",
    "inhalt",
    "indice",
    "contenido",
    "contenidos",
}
_PAGE_LABEL = r"(?:\d{1,4}|[ivxlcdmIVXLCDM]{1,10})"
_LEADER_ENTRY = re.compile(
    rf"(?P<title>.+?)\s*(?P<leader>(?:(?:[.·_]\s*){{2,}}|…+))\s*"
    rf"(?P<label>{_PAGE_LABEL})(?=\s|$)"
)
_TRAILING_ENTRY = re.compile(rf"(?P<title>\S.*?)\s+(?P<label>{_PAGE_LABEL})$")
_LABEL_ONLY = re.compile(rf"^{_PAGE_LABEL}$")
_NUMBERED_TITLE = re.compile(r"^(?P<number>\d+(?:\.\d+)+)\.?\s+")
_FOOTNOTE_SHAPED = re.compile(
    r"^\s*(?:\[\s*\d+\s*\]|\d+|[†‡*]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+|[A-Za-z])"
    r"(?:[.)])?(?=\s|$)"
)


@dataclass(frozen=True, slots=True)
class PrintedContentsPage:
    """Recognized entries and source blocks belonging to one printed TOC page."""

    entries: tuple[PrintedTocEntry, ...]
    entry_block_ids: frozenset[str]
    entries_by_block_id: dict[str, tuple[PrintedTocEntry, ...]]
    heading: SourceTextBlock | None
    bbox: BoundingBox
    show_heading: bool = True

    @property
    def protected_block_ids(self) -> frozenset[str]:
        if self.heading is None:
            return self.entry_block_ids
        return self.entry_block_ids | {self.heading.id}


@dataclass(frozen=True, slots=True)
class _ParsedEntries:
    entries: tuple[PrintedTocEntry, ...]
    consumed_ids: frozenset[str]
    entries_by_block_id: dict[str, tuple[PrintedTocEntry, ...]]
    strong_entry_count: int
    bbox: BoundingBox | None


@dataclass(frozen=True, slots=True)
class _EntryCandidate:
    entry: PrintedTocEntry
    source_ids: frozenset[str]
    anchor_id: str
    bbox: BoundingBox
    ordinal: int
    strong: bool


def detect_printed_contents_pages(
    pages: list[ParsedPage],
    ignored_geometric_ids: set[str] | None = None,
    ignored_continuation_ids: set[str] | None = None,
) -> dict[int, PrintedContentsPage]:
    """Recognize explicit TOC pages and adjacent continuation pages."""
    detected: dict[int, PrintedContentsPage] = {}
    ignored_geometric_ids = ignored_geometric_ids or set()
    ignored_continuation_ids = ignored_continuation_ids or set()
    previous: PrintedContentsPage | None = None
    for page in pages:
        heading = _contents_heading(page)
        candidates = [
            block
            for block in page.text_blocks
            if block.id != getattr(heading, "id", None)
            and (heading is None or block.bbox.y0 >= heading.bbox.y0)
        ]
        ignored_ids = set(ignored_geometric_ids)
        if heading is None:
            ignored_ids.update(ignored_continuation_ids)
        parsed = _parse_entries(page, candidates, ignored_ids)
        explicit = heading is not None and _has_enough_evidence(parsed)
        continuation = (
            heading is None
            and previous is not None
            and _is_continuation(page, parsed, previous)
        )
        if not (explicit or continuation) or parsed.bbox is None:
            previous = None
            continue
        bbox = parsed.bbox.union(heading.bbox) if heading is not None else parsed.bbox
        contents = PrintedContentsPage(
            entries=parsed.entries,
            entry_block_ids=parsed.consumed_ids,
            entries_by_block_id=parsed.entries_by_block_id,
            heading=heading,
            bbox=bbox,
            show_heading=heading is not None and previous is None,
        )
        detected[page.number] = contents
        previous = contents
    return detected


def _has_enough_evidence(parsed: _ParsedEntries) -> bool:
    return len(parsed.entries) >= 2 and (
        parsed.strong_entry_count >= 1 or len(parsed.entries) >= 3
    )


def _is_continuation(
    page: ParsedPage,
    parsed: _ParsedEntries,
    previous: PrintedContentsPage,
) -> bool:
    return (
        len(parsed.entries) >= 3
        and parsed.strong_entry_count >= 2
        and parsed.bbox is not None
        and abs(parsed.bbox.x0 - previous.bbox.x0) <= page.width * 0.15
    )


def _contents_heading(page: ParsedPage) -> SourceTextBlock | None:
    ordered = sorted(page.text_blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))
    matches = [
        block
        for block in ordered[:6]
        if block.bbox.y0 <= page.height * 0.3
        and _heading_key(block.text) in _CONTENTS_HEADINGS
    ]
    return min(matches, key=lambda block: (block.bbox.y0, block.bbox.x0), default=None)


def _heading_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_text(value).casefold())
    ascii_letters = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z]+", "", ascii_letters)


def _parse_entries(
    page: ParsedPage,
    blocks: list[SourceTextBlock],
    ignored_geometric_ids: set[str],
) -> _ParsedEntries:
    geometric = _geometric_entries(page, blocks, ignored_geometric_ids)
    geometric_ids = {source_id for candidate in geometric for source_id in candidate.source_ids}
    ordered = _toc_reading_order(
        page, [block for block in blocks if block.id not in geometric_ids]
    )
    textual, trailing = _textual_entries(page, ordered, ignored_geometric_ids)
    raw_strong = [*geometric, *textual]
    regular_strong = [
        candidate
        for candidate in raw_strong
        if not _is_bottom_footnote_candidate(page, candidate, blocks)
    ]
    bottom_strong = [
        candidate
        for candidate in raw_strong
        if _is_bottom_footnote_candidate(page, candidate, blocks)
    ]
    regular_trailing = [
        candidate
        for candidate in trailing
        if not _is_bottom_footnote_candidate(page, candidate, blocks)
    ]
    accepted_bottom_strong = _accepted_bottom_strong_candidates(
        page, bottom_strong, regular_strong, blocks
    )
    accepted_trailing: list[_EntryCandidate] = []
    if regular_strong or len(regular_trailing) >= 3:
        independent_trailing_ids = _independent_trailing_candidate_ids(
            page, regular_trailing, blocks
        )
        accepted_trailing = [
            candidate
            for candidate in regular_trailing
            if not regular_strong
            or id(candidate) in independent_trailing_ids
            or _matches_toc_context(page, candidate, regular_strong, blocks)
        ]

    context_candidates = [*regular_strong, *accepted_bottom_strong, *accepted_trailing]
    if not context_candidates and len(regular_trailing) >= 2:
        context_candidates = regular_trailing
    accepted_bottom = [
        candidate
        for candidate in trailing
        if _is_bottom_footnote_candidate(page, candidate, blocks)
        and _matches_toc_context(page, candidate, context_candidates, blocks)
    ]
    candidates = [
        *regular_strong,
        *accepted_bottom_strong,
        *accepted_trailing,
        *accepted_bottom,
    ]
    candidates = _sort_candidates(page, candidates)

    seen: set[tuple[str, str, int]] = set()
    unique: list[_EntryCandidate] = []
    for candidate in candidates:
        key = (candidate.entry.title, candidate.entry.page_label, candidate.entry.level)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    consumed_ids = frozenset(
        source_id for candidate in unique for source_id in candidate.source_ids
    )
    return _ParsedEntries(
        tuple(candidate.entry for candidate in unique),
        consumed_ids,
        _entries_by_block_id(unique),
        sum(candidate.strong for candidate in unique),
        _union_boxes([candidate.bbox for candidate in unique]),
    )


def _entries_by_block_id(
    candidates: list[_EntryCandidate],
) -> dict[str, tuple[PrintedTocEntry, ...]]:
    result: dict[str, list[PrintedTocEntry]] = {}
    for candidate in candidates:
        result.setdefault(candidate.anchor_id, []).append(candidate.entry)
    return {source_id: tuple(entries) for source_id, entries in result.items()}


def _toc_reading_order(page: ParsedPage, blocks: list[SourceTextBlock]) -> list[SourceTextBlock]:
    if len(blocks) < 4:
        return sorted(blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))
    resolver = ReadingOrderResolver()
    clusters = resolver.detect_columns(blocks, page.width)
    if len(clusters) < 2:
        return sorted(blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))
    starts = [median(block.bbox.x0 for block in cluster) for cluster in clusters]
    assigned = [list(cluster) for cluster in clusters]
    clustered_ids = {block.id for cluster in clusters for block in cluster}
    for block in blocks:
        if block.id in clustered_ids:
            continue
        index = min(range(len(starts)), key=lambda item: abs(block.bbox.x0 - starts[item]))
        assigned[index].append(block)
    return [
        block
        for cluster in assigned
        for block in sorted(cluster, key=lambda item: (item.bbox.y0, item.bbox.x0))
    ]


def _textual_entries(
    page: ParsedPage,
    blocks: list[SourceTextBlock],
    ignored_trailing_ids: set[str],
) -> tuple[list[_EntryCandidate], list[_EntryCandidate]]:
    candidates: list[_EntryCandidate] = []
    trailing: list[_EntryCandidate] = []
    pending: tuple[str, SourceTextBlock] | None = None
    invalid_ids: set[str] = set()
    previous_unlabeled: tuple[str, SourceTextBlock] | None = None
    ordinal = 0

    for block in blocks:
        text = normalize_text(block.text)
        if block.id in ignored_trailing_ids:
            if pending is not None:
                invalid_ids.add(pending[1].id)
                pending = None
            previous_unlabeled = None
            continue
        matches = list(_LEADER_ENTRY.finditer(text))
        if matches:
            use_pending = pending is not None and _can_continue(pending[1], block, page)
            use_previous = (
                pending is None
                and previous_unlabeled is not None
                and _can_prepend(previous_unlabeled[1], block, page)
            )
            if pending is not None and not use_pending:
                invalid_ids.add(pending[1].id)
            for index, match in enumerate(matches):
                title = _clean_title(match.group("title"))
                source_ids = {block.id}
                bbox = block.bbox
                if index == 0 and use_pending and pending is not None:
                    title = normalize_text(f"{pending[0]} {title}")
                    source_ids.add(pending[1].id)
                    bbox = pending[1].bbox.union(bbox)
                elif index == 0 and use_previous and previous_unlabeled is not None:
                    title = normalize_text(f"{previous_unlabeled[0]} {title}")
                    source_ids.add(previous_unlabeled[1].id)
                    bbox = previous_unlabeled[1].bbox.union(bbox)
                if not title:
                    invalid_ids.add(block.id)
                    continue
                candidates.append(
                    _EntryCandidate(
                        _entry(title, match.group("label")),
                        frozenset(source_ids),
                        block.id,
                        bbox,
                        ordinal,
                        True,
                    )
                )
                ordinal += 1
            remainder = _clean_title(text[matches[-1].end() :])
            pending = (remainder, block) if remainder else None
            previous_unlabeled = None
            continue

        if pending is not None:
            invalid_ids.add(pending[1].id)
            pending = None
        match = _TRAILING_ENTRY.fullmatch(text)
        if match is not None:
            title = _clean_title(match.group("title"))
            if title:
                trailing.append(
                    _EntryCandidate(
                        _entry(title, match.group("label")),
                        frozenset({block.id}),
                        block.id,
                        block.bbox,
                        ordinal,
                        False,
                    )
                )
                ordinal += 1
            previous_unlabeled = None
        else:
            previous_unlabeled = (text, block) if text else None

    if pending is not None:
        invalid_ids.add(pending[1].id)
    while True:
        linked_ids = {
            source_id
            for candidate in candidates
            if candidate.source_ids.intersection(invalid_ids)
            for source_id in candidate.source_ids
        }
        if linked_ids.issubset(invalid_ids):
            break
        invalid_ids.update(linked_ids)
    candidates = [
        candidate
        for candidate in candidates
        if not candidate.source_ids.intersection(invalid_ids)
    ]
    return candidates, trailing


def _geometric_entries(
    page: ParsedPage,
    blocks: list[SourceTextBlock],
    ignored_ids: set[str],
) -> list[_EntryCandidate]:
    pairs: list[tuple[SourceTextBlock, SourceTextBlock]] = []
    labels = [
        block
        for block in blocks
        if block.id not in ignored_ids and _LABEL_ONLY.fullmatch(normalize_text(block.text))
    ]
    for label in labels:
        tolerance = max(label.font_size, 8.0) * 0.8
        titles = [
            block
            for block in blocks
            if block.id not in ignored_ids
            and block.id != label.id
            and not _LABEL_ONLY.fullmatch(normalize_text(block.text))
            and block.bbox.x0 < label.bbox.x0
            and abs(block.bbox.center_y - label.bbox.center_y) <= tolerance
            and block.bbox.width < page.width * 0.9
        ]
        if not titles:
            continue
        title_block = max(titles, key=lambda block: block.bbox.x1)
        title = _clean_title(title_block.text)
        if not title:
            continue
        pairs.append((title_block, label))

    aligned_groups: list[list[tuple[SourceTextBlock, SourceTextBlock]]] = []
    tolerance = page.width * 0.04
    for pair in sorted(pairs, key=lambda item: item[1].bbox.x0):
        if (
            not aligned_groups
            or pair[1].bbox.x0
            - median(item[1].bbox.x0 for item in aligned_groups[-1])
            > tolerance
        ):
            aligned_groups.append([pair])
        else:
            aligned_groups[-1].append(pair)

    result: list[_EntryCandidate] = []
    ordinal = 0
    for group in aligned_groups:
        if len(group) < 2:
            continue
        for title_block, label in group:
            result.append(
                _EntryCandidate(
                    _entry(_clean_title(title_block.text), normalize_text(label.text)),
                    frozenset({title_block.id, label.id}),
                    title_block.id,
                    title_block.bbox.union(label.bbox),
                    ordinal,
                    True,
                )
            )
            ordinal += 1
    return result


def _can_continue(
    previous: SourceTextBlock,
    current: SourceTextBlock,
    page: ParsedPage,
) -> bool:
    gap = current.bbox.y0 - previous.bbox.y1
    return (
        previous.page_number == current.page_number
        and -max(previous.font_size, current.font_size) <= gap
        <= max(previous.font_size, current.font_size) * 3
        and abs(previous.bbox.x0 - current.bbox.x0) <= page.width * 0.15
    )


def _can_prepend(
    previous: SourceTextBlock,
    current: SourceTextBlock,
    page: ParsedPage,
) -> bool:
    text = normalize_text(previous.text)
    return (
        bool(text)
        and not text.endswith((".", "!", "?", ";", ":"))
        and not _LABEL_ONLY.fullmatch(text)
        and _can_continue(previous, current, page)
        and abs(previous.font_size - current.font_size)
        <= max(1.5, current.font_size * 0.2)
    )


def _matches_toc_context(
    page: ParsedPage,
    candidate: _EntryCandidate,
    strong_candidates: list[_EntryCandidate],
    blocks: list[SourceTextBlock],
) -> bool:
    block_by_id = {block.id: block for block in blocks}
    candidate_blocks = [
        block_by_id[source_id]
        for source_id in candidate.source_ids
        if source_id in block_by_id
    ]
    strong_blocks = [
        block_by_id[source_id]
        for strong in strong_candidates
        for source_id in strong.source_ids
        if source_id in block_by_id
    ]
    if not candidate_blocks or not strong_blocks:
        return False
    body_size = median(block.font_size for block in strong_blocks)
    candidate_size = median(block.font_size for block in candidate_blocks)
    if abs(candidate_size - body_size) > max(1.0, body_size * 0.15):
        return False
    return any(
        abs(candidate.bbox.x0 - strong.bbox.x0) <= page.width * 0.15
        for strong in strong_candidates
    )


def _accepted_bottom_strong_candidates(
    page: ParsedPage,
    candidates: list[_EntryCandidate],
    regular_candidates: list[_EntryCandidate],
    blocks: list[SourceTextBlock],
) -> list[_EntryCandidate]:
    if regular_candidates:
        return [
            candidate
            for candidate in candidates
            if _matches_toc_context(page, candidate, regular_candidates, blocks)
        ]
    if len(candidates) < 2:
        return []
    accepted_ids = _independent_trailing_candidate_ids(page, candidates, blocks)
    return [candidate for candidate in candidates if id(candidate) in accepted_ids]


def _is_bottom_footnote_candidate(
    page: ParsedPage,
    candidate: _EntryCandidate,
    blocks: list[SourceTextBlock],
) -> bool:
    block_by_id = {block.id: block for block in blocks}
    return any(
        block.bbox.y0 >= page.height * 0.68
        and _FOOTNOTE_SHAPED.match(normalize_text(block.text)) is not None
        for source_id in candidate.source_ids
        if (block := block_by_id.get(source_id)) is not None
    )


def _independent_trailing_candidate_ids(
    page: ParsedPage,
    candidates: list[_EntryCandidate],
    blocks: list[SourceTextBlock],
) -> set[int]:
    if len(candidates) < 3:
        return set()
    block_by_id = {block.id: block for block in blocks}
    ordered = sorted(candidates, key=lambda candidate: candidate.bbox.x0)
    clusters: list[list[_EntryCandidate]] = [[ordered[0]]]
    for candidate in ordered[1:]:
        if candidate.bbox.x0 - median(item.bbox.x0 for item in clusters[-1]) > (
            page.width * 0.15
        ):
            clusters.append([candidate])
        else:
            clusters[-1].append(candidate)

    accepted: set[int] = set()
    for cluster in clusters:
        if len(cluster) < 3:
            continue
        source_blocks = [
            block_by_id[source_id]
            for candidate in cluster
            for source_id in candidate.source_ids
            if source_id in block_by_id
        ]
        if not source_blocks:
            continue
        font_sizes = [block.font_size for block in source_blocks]
        body_size = median(font_sizes)
        if max(abs(size - body_size) for size in font_sizes) > max(1.5, body_size * 0.2):
            continue
        accepted.update(id(candidate) for candidate in cluster)
    return accepted


def _sort_candidates(
    page: ParsedPage,
    candidates: list[_EntryCandidate],
) -> list[_EntryCandidate]:
    if not candidates:
        return []
    tolerance = page.width * 0.15
    by_x = sorted(candidates, key=lambda candidate: candidate.bbox.x0)
    clusters: list[list[_EntryCandidate]] = [[by_x[0]]]
    for candidate in by_x[1:]:
        if candidate.bbox.x0 - median(item.bbox.x0 for item in clusters[-1]) > tolerance:
            clusters.append([candidate])
        else:
            clusters[-1].append(candidate)
    valid = [cluster for cluster in clusters if len(cluster) >= 2]
    if 2 <= len(valid) <= 3:
        starts = [median(candidate.bbox.x0 for candidate in cluster) for cluster in valid]
        if min(right - left for left, right in zip(starts, starts[1:], strict=False)) >= (
            page.width * 0.18
        ):
            assigned = [list(cluster) for cluster in valid]
            valid_ids = {id(candidate) for cluster in valid for candidate in cluster}
            for candidate in candidates:
                if id(candidate) in valid_ids:
                    continue
                index = min(
                    range(len(starts)),
                    key=lambda item: abs(candidate.bbox.x0 - starts[item]),
                )
                assigned[index].append(candidate)
            return [
                candidate
                for cluster in assigned
                for candidate in sorted(
                    cluster,
                    key=lambda item: (item.bbox.y0, item.bbox.x0, item.ordinal),
                )
            ]
    return sorted(
        candidates,
        key=lambda candidate: (candidate.bbox.y0, candidate.bbox.x0, candidate.ordinal),
    )


def _entry(title: str, page_label: str) -> PrintedTocEntry:
    number = _NUMBERED_TITLE.match(title)
    level = min(3, number.group("number").count(".")) if number else 0
    return PrintedTocEntry(title=title, page_label=page_label, level=level)


def _clean_title(value: str) -> str:
    return normalize_text(value).strip(" .·…_–—-")


def _union_boxes(boxes: list[BoundingBox]) -> BoundingBox | None:
    if not boxes:
        return None
    result = boxes[0]
    for box in boxes[1:]:
        result = result.union(box)
    return result
