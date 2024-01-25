from absl import logging

import os
import shutil
import subprocess


from iceberg.utils import temp_filename, temp_directory
from iceberg import DrawableWithChild, Color
from iceberg.primitives.svg import SVG


class TypstError(Exception):
    pass


def _postprocess_typst_svg(svg_file: str):
    """Postprocess the SVG file generated by Typst.

    Modifies the SVG file in-place to make it compatible with Skia.

    Args:
        svg_file: The SVG file to postprocess.
    """

    from lxml import etree

    # Load SVG file
    svg = etree.parse(svg_file)

    # In defs, find all symbols with a single path child, and replace the symbol with the path.
    # Also put the symbol id on the path.
    for symbol in svg.xpath(
        "//svg:defs/svg:symbol", namespaces={"svg": "http://www.w3.org/2000/svg"}
    ):
        if len(symbol) == 1 and symbol[0].tag == "{http://www.w3.org/2000/svg}path":
            symbol[0].attrib["id"] = symbol.attrib["id"]
            symbol.getparent().replace(symbol, symbol[0])

    # Write SVG file.
    svg.write(svg_file, encoding="utf-8", xml_declaration=True)


def _create_typst_svg(typst_source: str, svg_file: str):
    _PROGRAM = "typst"

    # Check if program is installed.
    if shutil.which(_PROGRAM.split()[0]) is None:
        raise TypstError(
            f"Program '{_PROGRAM.split()[0]}' is not installed for Typst rendering. "
            f"Please install it and make it available in your PATH environment variable."
            f"You can find instructions at https://github.com/typst/typst"
        )

    # Write tex file
    root, _ = os.path.splitext(svg_file)
    with open(root + ".typ", "w", encoding="utf-8") as typst_file:
        typst_file.write(typst_source)

    # # tex to dvi
    # if os.system(
    #     " ".join(
    #         (
    #             _PROGRAM,
    #             "compile",
    #             f'"{root}.typ"',
    #             f'"{root}.svg"',
    #             ">",
    #             os.devnull,
    #         )
    #     )
    # ):
    #     logging.error("Typst Error! Not a worry, it happens to the best of us.")
    #     # TODO: Read the error message from stderr.
    #     raise TypstError("Typst Error!")

    # Use subprocess instead of os.system, so we can capture stderr.
    try:
        subprocess.run(
            [
                _PROGRAM,
                "compile",
                f"{root}.typ",
                f"{root}.svg",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode("utf-8")
        logging.error(f"Typst Error! {error_message}")
        raise TypstError(error_message)
    finally:
        # Cleanup superfluous documents
        for ext in [".typ"]:
            try:
                os.remove(root + ext)
            except FileNotFoundError:
                pass

    # Postprocess SVG
    _postprocess_typst_svg(svg_file)


def typst_content_to_svg_file(
    content: str,
) -> str:
    svg_file = os.path.join(temp_directory(), temp_filename(typst=content) + ".svg")
    if not os.path.exists(svg_file):
        _create_typst_svg(content, svg_file)
    return svg_file


class Typst(DrawableWithChild):
    """A Typst object, which renders Typst code.

    Args:
        typst: The Typst code to render.
        svg_scale: The scale of the SVG.
        color: The color of the SVG.
    """

    typst: str
    svg_scale: float = 1.0
    color: Color = Color(0, 0, 0, 1)

    def setup(self) -> None:
        svg_filename = typst_content_to_svg_file(self.typst)
        self._svg = SVG(svg_filename=svg_filename, color=self.color)
        self.set_child(self._svg.scale(self.svg_scale))


class MathTypst(DrawableWithChild):
    """A Typst object, which renders Typst math.

    Args:
        typst_math: The Typst math code to render.
        svg_scale: The scale of the SVG.
        color: The color of the SVG.
    """

    typst_math: str
    svg_scale: float = 1.0
    color: Color = Color(0, 0, 0, 1)

    def __init__(
        self, typst_math: str, svg_scale: float = 1.0, color: Color = Color(0, 0, 0, 1)
    ):
        self.init_from_fields(typst_math=typst_math, svg_scale=svg_scale, color=color)

    def setup(self) -> None:
        typst = (
            f"#set page(width: auto, height: auto, margin: 0cm)\n$ {self.typst_math} $"
        )

        self.set_child(Typst(typst=typst, svg_scale=self.svg_scale, color=self.color))
