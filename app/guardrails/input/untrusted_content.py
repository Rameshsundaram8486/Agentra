"""Wraps uploaded/retrieved content as clearly delimited untrusted data before it goes into a prompt.

The content cannot close its own wrapper: any closing tag with the wrapper's name inside it is defused.
"""

import re

_TAG = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


def _attribute(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(tag: str, content: str, **attributes: str) -> str:
    if not _TAG.match(tag):
        raise ValueError(f"invalid wrapper tag {tag!r}")
    defused = re.sub(rf"</\s*{tag}\s*>", f"</{tag}_text>", content, flags=re.IGNORECASE)
    attrs = "".join(f' {name}="{_attribute(value)}"' for name, value in attributes.items())
    return f"<{tag}{attrs}>\n{defused}\n</{tag}>"
