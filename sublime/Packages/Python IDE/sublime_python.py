import sys
import os
import socket
import time
import itertools
import subprocess
import pipes
import threading
import xmlrpc.client
import sublime
import sublime_plugin

# contains root paths for each view, see root_folder_for()
ROOT_PATHS = {}
# contains proxy objects for external Python processes, by interpreter used
PROXIES = {}
# lock for aquiring proxy instances
PROXY_LOCK = threading.RLock()
# contains errors found by PyFlask
ERRORS_BY_LINE = {}
# saves positions on goto_definition
GOTO_STACK = []

# for debugging the server, start it manually, e.g., "python <path_to_>/server.py <port>" and set the port here
DEBUG_PORT = None

# Constants
SERVER_SCRIPT = pipes.quote(os.path.join(
    os.path.dirname(__file__), "server/server.py"))
RETRY_CONNECTION_LIMIT = 5
HEARTBEAT_FREQUENCY = 9
DRAW_TYPE = 4 | 32
NO_ROOT_PATH = -1


def get_setting(key, view=None, default_value=None):
    if view is None:
        view = sublime.active_window().active_view()
    try:
        settings = view.settings()
        if settings.has(key):
            return settings.get(key)
    except:
        pass
    s = sublime.load_settings('SublimePython.sublime-settings')
    return s.get(key, default_value)

class DebugProcDummy(object):
    '''used only for debugging, when the server process is started externally'''
    def poll():
        return None
    def terminate():
        pass

class Proxy(object):
    '''Abstracts the external Python processes that do the actual
    work. SublimePython just calls local methods on Proxy objects.
    The Proxy objects start external Python processes, send them heartbeat
    messages, communicate with them and restart them if necessary.'''
    def __init__(self, python):
        self.python = python
        self.proc = None
        self.proxy = None
        self.port = None
        self.restart()

    def get_free_port(self):
        s = socket.socket()
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def restart(self):
        if DEBUG_PORT is None:
            self.port = self.get_free_port()
            self.proc = subprocess.Popen(
                "%s %s %i" % (self.python, SERVER_SCRIPT, self.port),
                shell=True
            )
            print("starting server on port %i with %s" % (self.port, self.python))
        else:
            self.port = DEBUG_PORT
            self.proc = DebugProcDummy()
        self.proxy = xmlrpc.client.ServerProxy(
            'http://localhost:%i' % self.port, allow_none=True)
        self.set_heartbeat_timer()

    def set_heartbeat_timer(self):
        sublime.set_timeout_async(
            self.send_heartbeat, HEARTBEAT_FREQUENCY * 1000)

    def stop(self):
        self.proxy = None
        self.proc.terminate()

    def send_heartbeat(self):
        if self.proxy:
            self.proxy.heartbeat()
            self.set_heartbeat_timer()

    def __getattr__(self, attr):
        '''deletegate all other calls to the xmlrpc client.
        wait if the server process is still runnning, but not responding
        if the server process has died, restart it'''
        def wrapper(*args, **kwargs):
            if not self.proxy:
                self.restart()
                time.sleep(0.2)
            method = getattr(self.proxy, attr)
            result = None
            tries = 0
            while tries < RETRY_CONNECTION_LIMIT:
                try:
                    result = method(*args, **kwargs)
                    break
                except Exception:
                    tries += 1
                    if self.proc.poll() is None:
                        # just retry
                        time.sleep(0.2)
                    else:
                        # died, restart and retry
                        self.restart()
                        time.sleep(0.2)
            return result
        return wrapper


def proxy_for(view):
    '''retrieve an existing proxy for an external Python process.
    will automatically create a new proxy if non exists for the
    requested interpreter'''
    proxy = None
    with PROXY_LOCK:
        python = get_setting("python_interpreter", view, "")
        if python == "":
            python = "python"
        if python in PROXIES:
            proxy = PROXIES[python]
        else:
            proxy = Proxy(python)
            PROXIES[python] = proxy
    return proxy


def root_folder_for(view):
    '''returns the folder open in ST which contains
    the file open in this view. Used to determine the
    rope project directory (assumes directories open in
    ST == project directory)'''
    def in_directory(file_path, directory):
        directory = os.path.realpath(directory)
        file_path = os.path.realpath(file_path)
        return os.path.commonprefix([file_path, directory]) == directory
    file_name = view.file_name()
    root_path = None
    if file_name in ROOT_PATHS:
        root_path = ROOT_PATHS[file_name]
    else:
        for folder in view.window().folders():
            if in_directory(file_name, folder):
                root_path = folder
                ROOT_PATHS[file_name] = root_path

        # no folders found -> single file project
        if root_path is None:
            root_path = NO_ROOT_PATH
    return root_path


class PythonStopServerCommand(sublime_plugin.WindowCommand):
    def run(self, *args):
        with PROXY_LOCK:
            python = get_setting("python_interpreter", "")
            if python == "":
                python = "python"
            proxy = PROXIES.get(python, None)
            if proxy:
                proxy.stop()
                del PROXIES[python]


class PythonTestCommand(sublime_plugin.WindowCommand):
    def run(self, *args):
        view = self.window.active_view()
        proxy = proxy_for(view)
        print("projects:", proxy.list_projects())


class PythonCheckSyntaxListener(sublime_plugin.EventListener):
    def is_python_syntax(self, view):
        syntax = view.settings().get('syntax')
        return bool(syntax and ("Python" in syntax))

    def on_load_async(self, view):
        '''Check the file syntax on load'''
        if not self.is_python_syntax(view) or view.is_scratch():
            return
        self._check(view)

    def on_activated_async(self, view):
        '''Check the file syntax on activated'''
        if not self.is_python_syntax(view) or view.is_scratch():
            return
        self._check(view)

    def on_post_save_async(self, view):
        '''Check the file syntax on save'''
        if not self.is_python_syntax(view) or view.is_scratch():
            return
        self._check(view)

    def on_selection_modified_async(self, view):
        if (not self.is_python_syntax(view)
                or not get_setting('pyflakes_linting', view, True)):
            return

        vid = view.id()
        errors_by_line = ERRORS_BY_LINE.get(vid, None)

        if not errors_by_line:
            view.erase_status('sublimepython-errors')
            return

        lineno = view.rowcol(view.sel()[0].end())[0] + 1
        if lineno in errors_by_line:
            view.set_status('sublimepython-errors', '; '.join(
                [m['message'] % tuple(m['message_args'])
                    for m in errors_by_line[lineno]]
            ))
        else:
            view.erase_status('sublimepython-errors')

    def _check(self, view):
        if not get_setting('pyflakes_linting', view, True):
            return

        proxy = proxy_for(view)
        check_result = proxy.check_syntax(
            view.substr(sublime.Region(0, view.size())))
        # the result can be a list of errors, or single syntax exception
        if isinstance(check_result, list):
            by_line = lambda e: e['lineno']
            errors = sorted(check_result, key=by_line)
            errors_by_line = {}
            for k, g in itertools.groupby(errors, by_line):
                errors_by_line[k] = list(g)
            ERRORS_BY_LINE[view.id()] = errors_by_line
            self.visualize_errors(view, errors)
        else:
            self.handle_syntax_exception(view, check_result)
        self.on_selection_modified_async(view)

    def visualize_errors(self, view, errors):
        view.erase_regions('sublimepython-errors')
        errors_by_line = ERRORS_BY_LINE[view.id()]

        outlines = [view.line(view.text_point(lineno - 1, 0))
                    for lineno in errors_by_line.keys()]

        if outlines:
            view.add_regions(
                'sublimepython-errors', outlines, 'keyword', 'dot',
                DRAW_TYPE)
        else:
            view.erase_regions("sublimepython-errors")

    def handle_syntax_exception(self, view, e):
        if not get_setting('pyflakes_linting', view, True):
            return
        if e is None:
            return
        (lineno, offset, text) = e["lineno"], e["offset"], e["text"]

        if text is None:
            print >> sys.stderr, "SublimePython error decoding src file %s" % (
                self.filename)
        else:
            ERRORS_BY_LINE[view.id()] = {
                lineno: [{"message": "Syntax error", "message_args": ()}]}
            line = text.splitlines()[-1]
            if offset is not None:
                offset = offset - (len(text) - len(line))

            view.erase_regions('sublimepython-errors')
            if offset is not None:
                text_point = view.text_point(lineno - 1, 0) + offset
                view.add_regions(
                    'sublimepython-errors',
                    [sublime.Region(text_point, text_point + 1)],
                    'keyword', 'dot', DRAW_TYPE)
            else:
                view.add_regions(
                    'sublimepython-errors',
                    [view.line(view.text_point(lineno - 1, 0))],
                    'keyword', 'dot', DRAW_TYPE)


class PythonCompletionsListener(sublime_plugin.EventListener):
    '''Retrieves completion proposals from external Python
    processes running Rope'''
    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.python'):
            return []
        path = view.file_name()
        source = view.substr(sublime.Region(0, view.size()))
        loc = locations[0]
        # t0 = time.time()
        proxy = proxy_for(view)
        proposals = proxy.completions(source, root_folder_for(view), path, loc)
        # proposals = (
        #   proxy.profile_completions(source, root_folder_for(view), path, loc)
        # )
        # print("+++", time.time() - t0)
        if proposals:
            completion_flags = (
                sublime.INHIBIT_WORD_COMPLETIONS |
                sublime.INHIBIT_EXPLICIT_COMPLETIONS
            )
            return (proposals, completion_flags)
        return proposals

    def on_post_save_async(self, view, *args):
        proxy = proxy_for(view)
        path = view.file_name()
        proxy.report_changed(root_folder_for(view), path)


class PythonGetDocumentationCommand(sublime_plugin.WindowCommand):
    '''Retrieves the docstring for the identifier under the cursor and
    displays it in a new panel.'''
    def run(self):
        view = self.window.active_view()
        row, col = view.rowcol(view.sel()[0].a)
        offset = view.text_point(row, col)
        path = view.file_name()
        source = view.substr(sublime.Region(0, view.size()))
        if view.substr(offset) in [u'(', u')']:
            offset = view.text_point(row, col - 1)

        proxy = proxy_for(view)
        doc = proxy.documentation(source, root_folder_for(view), path, offset)
        if doc:
            open_pydoc_in_view = get_setting("open_pydoc_in_view")
            if open_pydoc_in_view:
                self.display_docs_in_view(doc)
            else:
                self.display_docs_in_panel(view, doc)
        else:
            word = view.substr(view.word(offset))
            self.notify_no_documentation(view, word)

    def notify_no_documentation(self, view, word):
        view.set_status(
            "rope_documentation_error",
            "No documentation found for %s" % word
        )

        def clear_status_callback():
            view.erase_status("rope_documentation_error")
        sublime.set_timeout_async(clear_status_callback, 5000)

    def display_docs_in_panel(self, view, doc):
        out_view = view.window().get_output_panel(
            "rope_python_documentation")
        out_view.run_command("simple_clear_and_insert", {"insert_string": doc})
        view.window().run_command(
            "show_panel", {"panel": "output.rope_python_documentation"})

    def display_docs_in_view(self, doc):
        create_view_in_same_group = get_setting("create_view_in_same_group")

        v = self.find_pydoc_view()
        if not v:
            active_group = self.window.active_group()
            if not create_view_in_same_group:
                if self.window.num_groups() == 1:
                    self.window.run_command('new_pane', {'move': False})
                if active_group == 0:
                    self.window.focus_group(1)
                else:
                    self.window.focus_group(active_group-1)

            self.window.new_file(sublime.TRANSIENT)
            v = self.window.active_view()
            v.set_name("*pydoc*")
            v.set_scratch(True)

        v.set_read_only(False)
        v.run_command("simple_clear_and_insert", {"insert_string": doc})
        v.set_read_only(True)
        self.window.focus_view(v)

    def find_pydoc_view(self):
        '''
        Return view named *pydoc* if exists, None otherwise.
        '''
        for w in self.window.views():
            if w.name() == "*pydoc*":
                return w
        return None

class SimpleClearAndInsertCommand(sublime_plugin.TextCommand):
    def run(self, edit, block=False, **kwargs):
        doc = kwargs['insert_string']
        r = sublime.Region(0, self.view.size())
        self.view.erase(edit, r)
        self.view.insert(edit, 0, doc)


class PythonGotoDefinitionCommand(sublime_plugin.WindowCommand):
    '''
    Shows the definition of the identifier under the cursor, project-wide.
    '''
    def run(self, *args):
        view = self.window.active_view()
        row, col = view.rowcol(view.sel()[0].a)
        offset = view.text_point(row, col)
        path = view.file_name()
        source = view.substr(sublime.Region(0, view.size()))
        if view.substr(offset) in [u'(', u')']:
            offset = view.text_point(row, col - 1)

        proxy = proxy_for(view)
        def_result = proxy.definition_location(
            source, root_folder_for(view), path, offset)

        if not def_result or def_result == [None, None]:
            return

        target_path, target_lineno = def_result
        current_lineno = view.rowcol(view.sel()[0].end())[0] + 1

        if None not in (path, target_path, target_lineno):
            self.save_pos(view.file_name(), current_lineno)
            path = target_path + ":" + str(target_lineno)
            self.window.open_file(path, sublime.ENCODED_POSITION)
        elif target_lineno is not None:
            self.save_pos(view.file_name(), current_lineno)
            path = view.file_name() + ":" + str(target_lineno)
            self.window.open_file(path, sublime.ENCODED_POSITION)
        else:
            # fail silently (user selected whitespace, etc)
            pass

    def save_pos(self, file_path, lineno):
        GOTO_STACK.append((file_path, lineno))


class PythonGoBackCommand(sublime_plugin.WindowCommand):
    def run(self, *args):
        if GOTO_STACK:
            file_name, lineno = GOTO_STACK.pop()
            path = file_name + ":" + str(lineno)
            self.window.open_file(path, sublime.ENCODED_POSITION)
