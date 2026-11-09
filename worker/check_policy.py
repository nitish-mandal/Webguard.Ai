"""Service-owned verification selectors. Copied into the prepared image, never repo-owned."""

REGRESSION_PATH = '/opt/webguard/regressions/test_pagination.py'
REGRESSION_PREFIX = '_webguard_regression/test_pagination.py::'
REGRESSION_IDS = tuple(REGRESSION_PREFIX + name for name in (
    'test_full_first', 'test_full_second', 'test_page_size_one', 'test_partial',
    'test_beyond_end', 'test_empty', 'test_negative_page', 'test_zero_size', 'test_negative_size',
))
DISCRIMINATING_IDS = REGRESSION_IDS[:3]


def check_command(base, check='suite', test_id=None, files=None):
    if not base or base[-1] != 'tests':
        raise ValueError('Unsupported trusted profile')
    if check == 'suite' and test_id is None:
        return list(base)
    if check == 'regression' and test_id is None:
        return [*base[:-1], '--', REGRESSION_PATH]
    if check == 'original' and isinstance(test_id, str) and len(test_id) <= 512:
        path = test_id.split('::')[0]
        if (test_id.startswith('tests/') and '::' in test_id and path.endswith('.py')
                and not any(part in ('', '.', '..') for part in path.split('/'))
                and '\\' not in test_id and not any(ord(char) < 32 for char in test_id)
                and (files is None or path in files)):
            return [*base[:-1], '--', test_id]
    raise ValueError('Invalid trusted check selector')
