from typing import List, Optional

from sphinx.ext.autodoc import ClassDocumenter, DataDocumenter, FunctionDocumenter, MethodDocumenter


class NoDocstringDocumenter(FunctionDocumenter):
    objtype = "function"
    option_spec = FunctionDocumenter.option_spec.copy()
    option_spec["no-docstring"] = lambda x: True

    def get_doc(self) -> Optional[List[List[str]]]:
        if "no-docstring" in self.options:
            return []
        return super().get_doc()


class NoDocstringMethodDocumenter(NoDocstringDocumenter, MethodDocumenter):  # type: ignore[misc]
    objtype = "method"


class NoDocstringClassDocumenter(NoDocstringDocumenter, ClassDocumenter):  # type: ignore[misc]
    objtype = "class"


class NoDocstringDataDocumenter(NoDocstringDocumenter, DataDocumenter):  # type: ignore[misc]
    objtype = "data"
