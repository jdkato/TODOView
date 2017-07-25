import os
import re

import sublime
import sublime_plugin

TEMPLATE = r'\b({0})(?:\((.+)\))?: (.+)$'
EXTRACT_PAT = None
EXTRACT_RE = None
PREFS = None


def plugin_loaded():
    """Initialize the extraction regexp.
    """
    global EXTRACT_RE, EXTRACT_PAT, PREFS
    # TODO: respect updates to settings
    settings = sublime.load_settings('TODOView.sublime-settings')
    PREFS = sublime.load_settings('Preferences.sublime-settings')
    EXTRACT_PAT = TEMPLATE.format('|'.join(settings.get('targets', [])))
    EXTRACT_RE = re.compile(EXTRACT_PAT)


def parse_query(query):
    """Parse a search query and return its individual parts.

    Args:
        query (str): A query in the form 'scope:TODO,...:assignee,...'.

    Returns:
        [str]: The parsed sections of the query.

    Examples:
        >>> parse_query('file:TODO:*')
        ['file', ['TODO'], ['*']]
    """
    if query == '':
        return ['*', ['*'], ['*']]
    elif not query.count(':') == 2:
        return []
    parts = query.split(':')
    categories = parts[1].split(',')
    assignees = parts[2].split(',')
    return [parts[0], categories, assignees]


def format_message(msg):
    """Format the given message.
    """
    if not any(msg.endswith(c) for c in ('.', '?', '!')) and len(msg) > 30:
        msg = msg + ' ...'
    return msg


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
        v = sublime.active_window().active_view().file_name()
        if not ignore_path(v):
            views.append(v)
    elif scope in ('open', 'o'):
        for v in sublime.active_window().views():
            name = v.file_name()
            if not ignore_path(name):
                views.append(name)
    else:
        for f in sublime.active_window().folders():
            for path, subdirs, files in os.walk(f):
                for name in files:
                    p = os.path.join(path, name)
                    if not ignore_path(p):
                        views.append(p)
    return views


def extract_comments_from_buffer(path, categories, assignees):
    """Extract all TODO-like comments from the given file.
    """
    matches = []
    try:
        with open(path) as buf:
            for i, line in enumerate(buf.readlines()):
                m = EXTRACT_RE.search(line)
                if m:
                    c = '*' in categories or m.group(1) in categories
                    a = '*' in assignees or m.group(2) in assignees
                    if c and a:
                        matches.append({
                            'position': (i, m.start(0)),
                            'category': m.group(1),
                            'assignee': m.group(2),
                            'message': format_message(m.group(3))
                        })
    except UnicodeDecodeError:
        pass
    return matches


def extract_comments(query):
    """Extract all TODO-like comments from the given sources.
    """
    comments = {}
    parsed = parse_query(query)
    if parsed == []:
        return comments

    scope, categories, assignees = parsed
    for v in aggregate_views(scope):
        found = extract_comments_from_buffer(v, categories, assignees)
        if found:
            comments[v] = found
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
        """Show the results in either a Quick Panel.
        """
        sublime.active_window().run_command(
            'todo_quick_panel', {'found': extract_comments(query)})


class TodoQuickPanelCommand(sublime_plugin.WindowCommand):
    """Show relevant TODOs in a Quick Panel.
    """
    positions = []

    def run(self, found):
        """Extract the comments and populate and Quick Panel with the results.
        """
        items = []
        for path, comments in found.items():
            for c in comments:
                self.positions.append((path, c['position']))
                if c['assignee']:
                    heading = '{0}({1})'.format(c['category'], c['assignee'])
                else:
                    heading = c['category']
                items.append([heading, c['message'], os.path.basename(path)])

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
