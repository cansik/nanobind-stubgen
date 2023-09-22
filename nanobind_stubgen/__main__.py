import argparse
from pathlib import Path

from nanobind_stubgen.NanobindStubsGenerator import NanobindStubsGenerator


def main():
    parser = argparse.ArgumentParser(prog="nanobind-stubgen",
                                     description="Nanobind Stubs Generator")
    parser.add_argument("module", type=str, help="Module to create stubs (e.g. nanogui).")
    parser.add_argument("--package", type=str, default=None, help="Optional package path to import module from.")
    parser.add_argument("--out", type=str, default=".", help="Output path for the generated pyi files.")
    args = parser.parse_args()

    generator = NanobindStubsGenerator(args.module, args.package)
    stubs = generator.analyse()

    output_path = Path(args.out)
    stubs.export(output_path)


if __name__ == "__main__":
    main()
