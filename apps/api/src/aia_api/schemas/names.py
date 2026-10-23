"""The name a person gives a client or a study."""

from typing import Annotated

from pydantic import StringConstraints

#: The blanks around a name are not part of it, and a name of blanks names nothing (UX audit F4).
EntityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
