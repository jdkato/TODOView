import os
import re

import sublime
import sublime_plugin

TEMPLATE = r'\b({0})(?:\((.+)\))?: (.+)$'
EXTRACT_RE = None
PREFS = None


def plugin_loaded():
    """Initialize the extraction regexp.
    """
    global EXTRACT_RE, PREFS
    # TODO: respect updates to settings
    settings = sublime.load_settings('TODOView.sublime-settings')
    PREFS = sublime.load_settings('Preferences.sublime-settings')
    EXTRACT_RE = TEMPLATE.format('|'.join(settings.get('targets', [])))


def parse_query(query):
    """Parse a search query and return its individual parts.

    Args:
        query (str): A query in the form 'scope:TODO,...:assignee,...:sort_by'.

    Returns:
        [str]: The parsed sections of the query.

    Examples:
        >>> parse_query('file:TODO:*:*')
        ['file', ['TODO'], ['*'], '*']
    """
    if not query.count(':') == 3:
        return []
    parts = query.split(':')
    categories = parts[1].split(',')
    assignees = parts[2].split(',')
    return [parts[0], categories, assignees, parts[3]]


def aggregate_views(scope):
    """Find all of the views we should search.

    Args:
        scope (str): The scope of our search. Accepted values are '(f)ile' (the
        view being edited), '(o)pen' (all open views), or '(a)ll' (all files
        in the current window).

    Returns:
        [sublime.View|str]: A list of View objects (when available) and file
        paths.
    """
    views = []
    if scope in ('file', 'f'):
        v = sublime.active_window().active_view()
        if not ignore_path(v.file_name()):
            views.append(v)
    elif scope in ('open', 'o'):
        for v in sublime.active_window().views():
            if not ignore_path(v.file_name()):
                views.append(v)
    else:
        for f in sublime.active_window().folders():
            for path, subdirs, files in os.walk(f):
                for name in files:
                    p = os.path.join(path, name)
                    if not ignore_path(p):
                        views.append(p)
    return views


def extract_comments_from_view(view):
    """Extract all TODO-like comments from the given view.
    """
    matches = []
    components = []
    found = view.find_all(EXTRACT_RE, 0, '\\1:\\2:\\3', components)
    captures = [m.split(':') for m in components]
    for i, region in enumerate(found):
        matches.append({
            'position': view.rowcol(region.begin()),
            'category': captures[i][0],
            'assignee': captures[i][1],
            'message': captures[i][2]
        })
    return matches


def ignore_path(path):
    """Determine if we should ignore the given path.
    """
    binary = PREFS.get('binary_file_patterns', [])
    files = PREFS.get('file_exclude_patterns', [])
    folders = PREFS.get('folder_exclude_patterns', [])
    for pat in folders + binary + files:
        if '*' in path and re.search(pat, path):
            return True
        elif pat in path:
            return True
    return False


def extract_comments_from_buffer(path):
    """Extract all TODO-like comments from the given file.
    """
    matches = []
    pat = re.compile(EXTRACT_RE)
    try:
        with open(path) as buf:
            for i, line in enumerate(buf.readlines()):
                m = pat.search(line)
                if m:
                    matches.append({
                        'position': (i, m.start(0)),
                        'category': m.group(1),
                        'assignee': m.group(2),
                        'message': m.group(3)
                    })
    except UnicodeDecodeError:
        pass
    return matches


def extract_comments(views):
    """Extract all TODO-like comments from the given sources.
    """
    comments = {}
    for v in views:
        if isinstance(v, sublime.View):
            comments[v.file_name()] = extract_comments_from_view(v)
        else:
            comments[v] = extract_comments_from_buffer(v)
    return comments


class TodoSearchCommand(sublime_plugin.WindowCommand):
    """Search for TODOs using the user-provided query string.
    """
    def run(self):
        """Prompt the user for a query.
        """
        self.window.show_input_panel(
            'Enter a query string: ', '', self.show_results, None, None)

    def show_results(self, query):
        """Show the results in either a Quick Panel or a Phantom.
        """
        parsed = parse_query(query)
        if parsed == []:
            return

        scope, categories, assignees, sort_by = parsed
        comments_by_view = extract_comments(aggregate_views(scope))

        filtered = {}
        for view, comments in comments_by_view.items():
            matches = []
            for c in comments:
                if (
                    (c['category'] in categories or '*' in categories) and
                    (c['assignee'] in assignees or '*' in assignees)
                ):
                    matches.append(c)

            filtered[view] = matches

        if sort_by in ('file', 'type', 'assignee'):
            filtered = sorted(filtered, key=lambda k: k[sort_by])

        sublime.active_window().run_command(
            'todo_quick_panel', {'found': filtered})


class TodoQuickPanelCommand(sublime_plugin.WindowCommand):
    """Show relevant TODOs in a Quick Panel.
    """
    positions = []

    def run(self, found):
        """Extract the comments and populate and Quick Panel with the results.
        """
        items = []
        for path, comments in found.items():
            display_path = path.lstrip(os.path.expanduser('~'))
            for c in comments:
                self.positions.append((path, c['position']))
                if c['assignee']:
                    heading = '{0}({1})'.format(c['category'], c['assignee'])
                else:
                    heading = c['category']
                items.append([heading, c['message'], display_path])

        if items:
            self.window.show_quick_panel(items, self.navigate)
        else:
            sublime.active_window().active_view().set_status(
                'TODOView', 'TODOView: no matches found')

    def navigate(self, idx):
        """Navigate the TODO comment.
        """
        if idx < 0:
            return
        f, p = self.positions[idx]
        self.window.open_file(
            '{0}:{1}:{2}'.format(f, p[0] + 1, p[1]), sublime.ENCODED_POSITION)
