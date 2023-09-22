import ast
import keyword
import logging
from typing import Tuple, Optional, Any
import re


def is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


def update_ndarray_signature(signature: str) -> str:
    # Replace "numpy.ndarray[...]" to "numpy.typing.NDArray"
    signature = re.sub(
        r"(numpy.)?ndarray\[.*?\]", "numpy.typing.NDArray", signature
    )
    return signature


def update_opaque_signature(signature: str) -> str:
    # Replace "<$type $object at $address>" to "..."
    signature = re.sub(r"<.* at 0x[0-9a-f]+>", "...", signature)
    return signature


def update_std_pair_signature(signature: str) -> str:
    # Replace "std::__1::pair<$a, $b>" to "Tuple[$a, $b]"
    # todo: handle recursive pairs (not possible with regex)
    signature = re.sub(r"std::__1::pair<([\w\_\.]*),\s*([\w\_\.]*)>", r"Tuple[\1, \2]", signature)
    return signature


def update_std_tuple_signature(signature: str) -> str:
    # Replace "std::__1::tuple<$a, $b, $c, $d>" to "Tuple[$a, $b]"
    # todo: handle recursive tuples (not possible with regex)
    signature = re.sub(r"std::__1::tuple<(.*)>", r"Tuple[\1]", signature)
    return signature


def update_tensor_signature(signature: str) -> str:
    # Replace "tensor[*]" with "numpy.typing.NDArray"
    # todo: handle tensor types
    signature = re.sub(r"tensor\[.*\]", r"numpy.typing.NDArray", signature)
    return signature


def post_process_signature(signature: str) -> str:
    signature = update_ndarray_signature(signature)
    signature = update_opaque_signature(signature)
    signature = update_std_pair_signature(signature)
    signature = update_std_tuple_signature(signature)
    signature = update_tensor_signature(signature)
    return signature


def parse_doc_signature(obj: Any, basic_signature: str) -> Tuple[str, Optional[str], Optional[str]]:
    doc = obj.__doc__
    if doc is None:
        return basic_signature, None, None

    doc_str = str(doc)
    parts = doc_str.split("\n")

    # todo: handle overloaded function
    signature = parts[0]
    doc = "\n".join([p for p in parts[1:]])
    func_name = signature.split("(")[0].strip()

    signature = post_process_signature(signature)

    return signature, doc, func_name


def parse_method_doc(name: str, obj: Any,
                     test_code: bool = True, suppress_warning: bool = False) -> Tuple[str, Optional[str]]:
    basic_signature = f"{name}(*args, **kwargs)"

    signature, doc, func_name = parse_doc_signature(obj, basic_signature)

    if keyword.iskeyword(func_name):
        logging.warning(f"Function is named like a python keyword ({func_name}): {signature}")

    if test_code:
        is_valid = is_valid_python(f"def {signature}:\n    pass")
        if not is_valid:
            if not suppress_warning:
                logging.warning(f"Function is not valid python code: {signature}")
            return basic_signature, None

    if not signature.startswith(name):
        return basic_signature, None

    return signature, doc
