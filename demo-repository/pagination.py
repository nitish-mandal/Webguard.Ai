def page_items(items: list, page: int, page_size: int) -> list:
    """Return a zero-based page. Intentional bug: exclusive end is one too small."""
    if page < 0 or page_size <= 0:
        raise ValueError("invalid pagination")
    start = page * page_size
    return items[start:start + page_size - 1]
