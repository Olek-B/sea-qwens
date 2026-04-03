# shared/indexer.py

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node
from shared.models import CodeFile, CodeFunction, CodeClass
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CallRelation:
    caller: str
    callee: str


@dataclass
class IndexResult:
    file: CodeFile
    classes: list[CodeClass] = field(default_factory=list)
    functions: list[CodeFunction] = field(default_factory=list)
    calls: list[CallRelation] = field(default_factory=list)


class CodeIndexer:
    """Parse source files using tree-sitter and extract code structure."""

    def __init__(self):
        self.PY_LANGUAGE = Language(tspython.language())
        self.parser = Parser(self.PY_LANGUAGE)

    def index_file(self, path: str, content: str, language: str) -> IndexResult:
        """Index a single source file."""
        code_file = CodeFile(path=path, language=language, content=content)
        if language == "python":
            return self._index_python(code_file)
        return IndexResult(file=code_file)

    def _index_python(self, code_file: CodeFile) -> IndexResult:
        tree = self.parser.parse(bytes(code_file.content, "utf8"))
        root = tree.root_node
        classes: list[CodeClass] = []
        functions: list[CodeFunction] = []
        calls: list[CallRelation] = []
        self._extract_definitions(root, code_file.path, classes, functions)
        self._extract_calls(root, functions, calls)
        return IndexResult(file=code_file, classes=classes, functions=functions, calls=calls)

    def _extract_definitions(
        self, node, file_path: str, classes: list, functions: list, parent_class: Optional[str] = None
    ):
        if node.type == "class_definition":
            cls = self._extract_class(node, file_path)
            classes.append(cls)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "function_definition":
                        func = self._extract_function(child, file_path, parent_class=cls.name)
                        functions.append(func)
        elif node.type == "function_definition":
            func = self._extract_function(node, file_path, parent_class)
            functions.append(func)
        for child in node.children:
            self._extract_definitions(child, file_path, classes, functions, parent_class)

    def _extract_class(self, node, file_path: str) -> CodeClass:
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf8") if name_node else "unknown"
        bases_node = node.child_by_field_name("superclasses")
        bases = []
        if bases_node:
            bases = [
                c.text.decode("utf8")
                for c in bases_node.children
                if c.type == "identifier"
            ]
        body_node = node.child_by_field_name("body")
        body_text = body_node.text.decode("utf8") if body_node else ""
        docstring = self._extract_docstring(body_node)
        return CodeClass(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            body=body_text,
            docstring=docstring,
            bases=bases,
        )

    def _extract_function(
        self, node, file_path: str, parent_class: Optional[str] = None
    ) -> CodeFunction:
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf8") if name_node else "unknown"
        body_node = node.child_by_field_name("body")
        body_text = body_node.text.decode("utf8") if body_node else ""
        lines = body_text.split("\n")
        signature = lines[0].strip() if lines else f"def {name}(...)"
        docstring = self._extract_docstring(body_node)
        return CodeFunction(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            body=body_text,
            signature=signature,
            docstring=docstring,
            is_method=parent_class is not None,
            parent_class=parent_class,
        )

    def _extract_docstring(self, body_node) -> str:
        if not body_node:
            return ""
        for child in body_node.children:
            if child.type == "expression_statement":
                string_node = child.children[0] if child.children else None
                if string_node and string_node.type == "string":
                    text = string_node.text.decode("utf8")
                    return text.strip('"""').strip("'''").strip()
        return ""

    def _extract_calls(self, node, functions: list, calls: list):
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = func_node.text.decode("utf8")
                func_name = callee.split(".")[-1]
                caller = self._find_enclosing_function(node, functions)
                if caller:
                    calls.append(CallRelation(caller=caller, callee=func_name))
        for child in node.children:
            self._extract_calls(child, functions, calls)

    def _find_enclosing_function(self, node, functions: list) -> Optional[str]:
        for func in functions:
            if (node.start_point[0] + 1) >= func.line_start and (
                node.end_point[0] + 1
            ) <= func.line_end:
                return func.name
        return None
