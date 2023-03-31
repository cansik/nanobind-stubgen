import ast
import importlib
import inspect
import keyword
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Tuple


class StubEntry(ABC):
    def __init__(self, name: str, obj: Any, sub_modules: Optional[List["StubEntry"]] = None):
        self.obj = obj
        self.name = name
        self.children = sub_modules if sub_modules is not None else []

    @property
    def import_path(self) -> str:
        return f"{inspect.getmodule(self.obj).__name__}"

    def __repr__(self):
        return f"{self.name}"

    @abstractmethod
    def export(self, output_path: Path, intent: int = 0):
        pass

    @staticmethod
    def _create_string(lines: List[str], intent: int) -> str:
        lines.append("\n")
        spacing = " " * intent * 4
        lines = [f"{spacing}{l}" for l in lines]
        return "\n".join(lines)

    def _create_doc(self, doc_str: Optional[str] = None) -> List[str]:
        out = []

        if doc_str is None:
            doc_str = self.obj.__doc__

        if doc_str is not None and str(doc_str).strip() != "":
            out.append(f"    \"\"\"")
            out.append(f"    {doc_str}")
            out.append(f"    \"\"\"")

        return out

    @property
    def has_children(self) -> bool:
        return len(self.children) > 0


class StubModule(StubEntry):

    def export(self, output_path: Path, intent: int = 0):
        print(f"exporting module {self.name}")

        if output_path.is_dir():
            os.makedirs(output_path, exist_ok=True)

        if self.has_sub_modules:
            output_path = output_path.joinpath(self.name)
            os.makedirs(output_path, exist_ok=True)

            module_path = output_path.joinpath("__init__.pyi")
        else:
            if output_path.is_file():
                output_path = output_path.parent

            module_path = output_path.joinpath(f"{self.name}.pyi")

        # create init file
        with open(module_path, "w"):
            pass

        for child in self.children:
            child.export(module_path)

    @property
    def has_sub_modules(self) -> bool:
        return len([child for child in self.children if isinstance(child, StubModule)]) > 0


class StubClass(StubEntry):
    def __init__(self, name: str, obj: Any):
        super().__init__(name, obj)

        self.annotations: List[str] = []
        self.super_classes: List[str] = []
        self.filter_child_type = set()

    def export(self, output_path: Path, intent: int = 0):
        super_classes_str = ", ".join(self.super_classes)
        if len(self.super_classes) > 0:
            super_classes_str = f"({super_classes_str})"

        out = [*self.annotations]
        out.append(f"class {self.name}{super_classes_str}:")
        out += self._create_doc()

        if not self.has_children:
            out.append("    ...")

        with open(output_path, "a") as f:
            text = self._create_string(out, intent)
            f.writelines(text)

        for child in self.children:
            # filter specific types
            if type(child) in self.filter_child_type:
                continue

            child.export(output_path, intent + 1)


class StubNanobindType(StubClass):
    pass


class StubNanobindEnum(StubClass):
    def __init__(self, name: str, obj: Any):
        super().__init__(name, obj)
        self.super_classes.append("Enum")
        self.filter_child_type.add(StubNanobindConstructor)


class StubNanobindEnumValue(StubEntry):
    def export(self, output_path: Path, intent: int = 0):
        out = [f"{self.name}"]

        with open(output_path, "a") as f:
            text = self._create_string(out, intent)
            f.writelines(text)


class StubRoutine(StubEntry):
    def __init__(self, name: str, obj: Any):
        super().__init__(name, obj)
        self.annotations: List[str] = []

    def export(self, output_path: Path, intent: int = 0):
        out = [*self.annotations]
        out.append(f"def {self.routine_signature()}:")
        out += self._create_doc()
        out.append(f"    ...")

        with open(output_path, "a") as f:
            text = self._create_string(out, intent)
            f.writelines(text)

    def __repr__(self):
        return f"{self.name}()"

    def routine_signature(self) -> str:
        return f"{self.name}(*args, **kwargs)"


class StubNanobindFunction(StubRoutine):
    def __init__(self, name: str, obj: Any):
        super().__init__(name, obj)

        signature, doc_str = self.parse_doc()
        self.signature = signature
        self.doc_str = doc_str

    @staticmethod
    def is_valid_python(code):
        try:
            ast.parse(code)
        except SyntaxError:
            return False
        return True

    def parse_doc(self) -> Tuple[str, Optional[str]]:
        doc = self.obj.__doc__
        if doc is None:
            return super().routine_signature(), None

        doc_str = str(doc)
        parts = doc_str.split("\n")

        # todo: handle overloaded function
        signature = parts[0]
        doc = "\n".join([p for p in parts[1:] if p.strip() != ""])
        func_name = signature.split("(")[0].strip()

        if keyword.iskeyword(func_name):
            logging.warning(f"Function is named like a python keyword ({func_name}): {signature}")

        is_valid = self.is_valid_python(f"def {signature}:\n    pass")
        if not is_valid:
            logging.warning(f"Function is not valid python code: {signature}")
            return super().routine_signature(), None

        if not signature.startswith(self.name):
            return super().routine_signature(), None

        return signature, doc

    def _create_doc(self, doc_str: Optional[str] = None) -> List[str]:
        return super()._create_doc(self.doc_str)

    def routine_signature(self) -> str:
        return self.signature


class StubNanobindMethod(StubNanobindFunction):
    pass


class StubNanobindConstructor(StubNanobindMethod):
    pass


class NanobindStubsGenerator:
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.module = importlib.import_module(self.module_name)

    def analyse(self) -> StubModule:
        result = self._analyse_module(self.module, StubModule(self.module_name, self.module))
        return result

    def _analyse_module(self, module, stub_entry: StubEntry) -> StubModule:
        for name, obj in inspect.getmembers(module):
            if name.startswith("_") and name != "__init__":
                continue

            has_been_used = False

            if inspect.isclass(obj):
                if type(obj).__name__ == "nb_type":
                    class_module = StubNanobindType(name, obj)
                elif type(obj).__name__ == "nb_enum":
                    class_module = StubNanobindEnum(name, obj)
                else:
                    class_module = StubClass(name, obj)
                has_been_used = True
                stub_entry.children.append(class_module)
                self._analyse_module(obj, class_module)

            if inspect.ismodule(obj):
                stub_module = StubModule(name, obj)
                stub_entry.children.append(stub_module)
                has_been_used = True
                self._analyse_module(obj, stub_module)

            if inspect.isroutine(obj):
                if type(obj).__name__ == "nb_method":
                    if name == "__init__":
                        stub_routine = StubNanobindConstructor(name, obj)
                    else:
                        stub_routine = StubNanobindMethod(name, obj)
                else:
                    if name == "__init__":
                        stub_routine = StubNanobindConstructor(name, obj)
                    else:
                        stub_routine = StubRoutine(name, obj)
                has_been_used = True
                stub_entry.children.append(stub_routine)

            if type(obj).__name__ == "nb_func":
                stub_nb_func = StubNanobindFunction(name, obj)
                stub_entry.children.append(stub_nb_func)
                has_been_used = True

            if isinstance(stub_entry, StubNanobindEnum) and isinstance(obj, module):
                stub_enum_value = StubNanobindEnumValue(name, obj)
                stub_entry.children.append(stub_enum_value)

            # todo: add support for enums
            # todo: add support for properties

            if not has_been_used:
                print(f"{inspect.getmodule(module).__name__}.{name}: {type(obj).__name__}")

        return stub_entry
