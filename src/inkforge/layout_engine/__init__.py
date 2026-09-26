"""Level 2: turn a Level 1 manifest + a per-newspaper profile into a layout plan.

This package only *plans* the layout (Python, fully testable without InDesign).
The actual InDesign document manipulation is a separate ExtendScript executor
(see ``extendscript/inkforge_layout.jsx``) that consumes the JSON this package
writes.
"""
