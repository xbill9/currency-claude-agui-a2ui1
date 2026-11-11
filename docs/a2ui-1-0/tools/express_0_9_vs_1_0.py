"""Compile one Express block to A2UI 0.9 and to A2UI 1.0 and compare.

usage: python3 express_0_9_vs_1_0.py
"""

import json

from a2ui.core.basic_catalog.v0_9 import BasicCatalog as Basic09
from a2ui.core.basic_catalog.v1_0 import BasicCatalog as Basic10
from a2ui.inference_formats.express import ExpressCompiler

SRC = """surface("main")
$/user/name = "Ada"
title = Text(formatString("Hello ${/user/name}"))
btn = Button(Text("Save"), action=Event("save", {name: $/user/name}, userMessage="Saving"))
root = Column([title, TextField("Name", $/user/name, checks=[?required("Name is required")]), btn])
"""


def compile_to(catalog, src):
    msgs = ExpressCompiler([catalog]).compile(src, surface_id="main")
    return [m.model_dump(by_alias=True, exclude_none=True) for m in msgs]


print("## Express source")
print(SRC)
v10 = compile_to(Basic10(), SRC)
print(
    "## A2UI 1.0:",
    len(v10),
    "message(s):",
    [k for m in v10 for k in m if k != "version"],
)
print(json.dumps(v10, indent=1))
src09 = SRC.replace(', userMessage="Saving"', "")
v09 = compile_to(Basic09(), src09)
print(
    "## A2UI 0.9 (userMessage removed):",
    len(v09),
    "message(s):",
    [k for m in v09 for k in m if k != "version"],
)
print(json.dumps(v09, indent=1))
print("## userMessage on 0.9")
try:
    compile_to(Basic09(), SRC)
except Exception as e:  # noqa: BLE001 - print whatever the compiler raises
    print(type(e).__name__ + ":", e)
