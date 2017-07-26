# TODOView

<p align="center">
  <img src="https://i.gyazo.com/8c11f28fda6459ee0babfa8a4c246ff8.gif">
</p>

TODOView offers an easy way to search for and navigate to TODO-like comments in your codebase. Navigation is controlled by *query strings* that have the following structure:

```text
scope:type(s):assignee(s)
```
where

- `scope` may be one of "(f)ile" (the active view only), "(o)pen" (all open views), or "\*" (any non-excluded file in the sidebar);
- `type(s)` is a comma-separated list of annotations to be included in the search (or "\*" to search for all `targets`, as listed in the settings file); and
- `assignee(s)` is a comma-separated list of [Google-style](https://google.github.io/styleguide/pyguide.html#TODO_Comments) identifiers (or "\*" to include all identifiers in the search).

For example, if we wanted to search for all TODOs or NOTEs assigned to `jdkato` in our currently open files, we'd use:

```text
open:TODO,NOTE:jdkato
```

A special case is the empty string, which is treated as `*:*:*`.
