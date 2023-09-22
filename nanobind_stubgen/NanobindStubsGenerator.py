import importlib
import inspect
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Tuple

from nanobind_stubgen import utils


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

        # split doc string for per-line indentation
        doc_str = str(doc_str).strip()
        doc_lines = [l.strip() for l in doc_str.split("\n")]

        if doc_str is not None and str(doc_str).strip() != "":
            out.append(f"    \"\"\"")
            for line in doc_lines:
                out.append(f"    {line}")
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
        out = [f"from typing import Any, Optional, overload, Typing, Sequence",
               f"from enum import Enum",
               f"import {self.import_path}"]

        with open(module_path, "w") as f:
            text = self._create_string(out, intent)
            f.writelines(text)

        for child in self.children:
            child.export(module_path)

    @property
    def has_sub_modules(self) -> bool:
        return len([child for child in self.children if isinstance(child, StubModule)]) > 0


class StubNanobindConstant(StubEntry):

    def export(self, output_path: Path, intent: int = 0):
        out = [f"{self.name}: {str(type(self.obj).__name__)}"]

        with open(output_path, "a") as f:
            text = self._create_string(out, intent)
            f.writelines(text)


class StubProperty(StubEntry):
    def __init__(self, name: str, obj: Any):
        super().__init__(name, obj)

        self.has_getter = obj.fget is not None
        self.has_setter = obj.fset is not None

    def export(self, output_path: Path, intent: int = 0):
        out = []

        if self.has_getter:
            out += self._create_getter()

        if self.has_setter:
            out += self._create_setter()

        with open(output_path, "a") as f:
            text = self._create_string(out, intent)
            f.writelines(text)

    def _create_signature(self, f) -> Tuple[str, Optional[str]]:
        signature, doc_str, func_name = utils.parse_doc_signature(f, f"{self.name}(*args, **kwargs)")

        if func_name == "<anonymous>":
            signature = signature.replace(func_name, self.name)

        # fix for missing function name
        if not signature.startswith(self.name):
            signature = f"{self.name}{signature}"

        return signature, doc_str

    def _create_method(self, f, annotation: str) -> []:
        signature, doc_str = self._create_signature(f)

        out = []
        out.append(f"@{annotation}")
        out.append(f"def {signature}:")

        if doc_str is not None:
            out += self._create_doc(doc_str)

        out.append("    ...")

        return out

    def _create_getter(self) -> []:
        return self._create_method(self.obj.fget, "property")

    def _create_setter(self) -> []:
        return self._create_method(self.obj.fset, f"{self.name}.setter")


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
        out = [f"{self.name}: Any"]

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


class StubNanobindOverloadFunction(StubRoutine):
    def __init__(self, name: str, obj: Any, signature: str, doc_str: str):
        super().__init__(name, obj)
        self.signature = signature
        self.doc_str = doc_str
        self.annotations.append("@overload")

    def _create_doc(self, doc_str: Optional[str] = None) -> List[str]:
        return super()._create_doc(self.doc_str)

    def routine_signature(self) -> str:
        return self.signature


class StubNanobindFunction(StubRoutine):
    def __init__(self, name: str, obj: Any, test_code: bool = True, suppress_warning: bool = False):
        super().__init__(name, obj)

        signature, doc_str = utils.parse_method_doc(name, obj, test_code, suppress_warning)
        self.signature = signature
        self.doc_str = doc_str

        self.add_overloads()

    def _create_doc(self, doc_str: Optional[str] = None) -> List[str]:
        return super()._create_doc(self.doc_str)

    def routine_signature(self) -> str:
        return self.signature

    def export(self, output_path: Path, intent: int = 0):
        super().export(output_path, intent)

        for child in self.children:
            child.export(output_path, intent)

    def add_overloads(self):
        overloads = self.detect_overloads()

        if overloads is None:
            return

        initial_fn = overloads.pop()
        self.signature = initial_fn[0]
        self.doc_str = initial_fn[1]

        self.signature = utils.post_process_signature(self.signature)

        for sig, doc in overloads:
            sig = utils.post_process_signature(sig)
            self.children.append(StubNanobindOverloadFunction(self.name, self.obj, sig, doc))

    def detect_overloads(self):
        # special handling for signatures only
        doc_str = self.obj.__doc__
        if doc_str is None:
            return

        lines = doc_str.splitlines()
        if len(lines) > 1 and all([l.startswith(self.name) for l in lines]):
            overloads = [(l, l) for l in lines]
            return overloads

        # handling overloads inside doc starting with number
        doc_str = self.doc_str
        if doc_str is None:
            return
        lines = doc_str.splitlines()

        fn_regex = r"\d+\.\s*``(?P<signature>.+)``"

        functions = []

        signature = self.signature
        doc = []

        for line in lines:
            matches = list(re.finditer(fn_regex, line, re.MULTILINE))

            if len(matches) > 0:
                functions.append((signature, "\n".join(doc)))
                signature = matches[0].group("signature")
                doc = []
                continue

            doc.append(line)

        functions.append((signature, "\n".join(doc)))

        if len(functions) > 1:
            return functions[1:]

        return functions


class StubNanobindMethod(StubNanobindFunction):
    pass


class StubNanobindConstructor(StubNanobindMethod):
    pass


class NanobindStubsGenerator:
    def __init__(self, module_name: str, package_name: Optional[str] = None):
        self.module_name = module_name
        self.module = importlib.import_module(self.module_name, package=package_name)

    def analyse(self) -> StubModule:
        result = self._analyse_module(self.module, StubModule(self.module_name, self.module))
        return result

    def _analyse_module(self, module: Any, stub_entry: StubEntry) -> StubModule:
        for name, obj in inspect.getmembers(module):
            if name.startswith("_") and name != "__init__":
                continue

            has_been_handled = False

            if inspect.isclass(obj):
                if type(obj).__name__ == "nb_type":
                    class_module = StubNanobindType(name, obj)
                elif type(obj).__name__ == "nb_enum":
                    class_module = StubNanobindEnum(name, obj)
                else:
                    class_module = StubClass(name, obj)
                has_been_handled = True
                stub_entry.children.append(class_module)
                self._analyse_module(obj, class_module)

            if inspect.ismodule(obj):
                stub_module = StubModule(name, obj)
                stub_entry.children.append(stub_module)
                has_been_handled = True
                self._analyse_module(obj, stub_module)

            if inspect.isroutine(obj):
                if type(obj).__name__ == "nb_method":
                    if name == "__init__":
                        stub_routine = StubNanobindConstructor(name, obj)
                    else:
                        stub_routine = StubNanobindMethod(name, obj)
                else:
                    if name == "__init__":
                        module_name = type(module).__name__
                        if module_name == "nb_enum" or module_name == "nb_type":
                            # todo: handle enum and type constructors
                            stub_routine = StubNanobindConstructor(name, obj, suppress_warning=True)
                        else:
                            stub_routine = StubNanobindConstructor(name, obj)
                    else:
                        stub_routine = StubRoutine(name, obj)
                has_been_handled = True
                stub_entry.children.append(stub_routine)

            if type(obj).__name__ == "nb_func":
                stub_nb_func = StubNanobindFunction(name, obj)
                stub_entry.children.append(stub_nb_func)
                has_been_handled = True

            if isinstance(stub_entry, StubNanobindEnum) and isinstance(obj, module):
                stub_enum_value = StubNanobindEnumValue(name, obj)
                stub_entry.children.append(stub_enum_value)
                has_been_handled = True

            if isinstance(obj, property):
                stub_property = StubProperty(name, obj)
                stub_entry.children.append(stub_property)
                has_been_handled = True

            # constants have not been handled
            if not has_been_handled:
                stub_constant = StubNanobindConstant(name, obj)
                stub_entry.children.append(stub_constant)
                has_been_handled = True

            if not has_been_handled:
                print(f"{inspect.getmodule(module).__name__}.{name}: {type(obj).__name__}")

        return stub_entry
