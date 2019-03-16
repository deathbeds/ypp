#!/usr/bin/env python
# coding: utf-8

# '''`ypp` (_pronounced Yippee!) helps manager your interactive state. `ypp.Output` objects are evented `traitlets` or `ipywidgets`
# that update as the interative state of an `IPython.InteractiveShell` is changed.  `ypp.Handler` objects are evented to change
# within special `globals` and `locals` namepsaces.
# '''

# Standard Library
import contextlib
import functools
import itertools
import sys

import IPython
import traitlets

try:
    import ipywidgets
except:
    ipywidgets = None

if __name__ == "__main__":
    get_ipython = IPython.get_ipython
    get_ipython().run_line_magic("reload_ext", "ypp")
    get_ipython().run_line_magic("reload_ext", "pidgin")


"""```import ypp
```"""


class Output(traitlets.HasTraits):
    """`Output` is the base class for the `ypp` interactive `ypp.TraitletOutput` & `ypp.WidgetOutput`.
>>> Output()
<...Output...>"""

    value = traitlets.Any()
    description = traitlets.Unicode()


class TraitletOutput(IPython.display.DisplayHandle, Output):
    """`TraitletOutput` is a non-`ipywidgets` interactive `Output` thats updates using the builtin
`IPython.display.DisplayHandle` system."""

    def _ipython_display_(TraitletOutput, before=None, after=None):
        """`TraitletOutput._ipython_display_` displays the `TraitletOutput.description` if it exists 
and then displays the `TraitletOutput.value`.  `TraitletOutput` manages updating existing display objects."""

        if TraitletOutput.description:
            IPython.display.display(IPython.display.Markdown("#### " + TraitletOutput.description))
        TraitletOutput.display(TraitletOutput.value)

    @traitlets.observe("value")
    def _change_value(TraitletOutput, change):
        """When `TraitletOutput.value` changes `TraitletOutput._change_value` triggers the `IPython.display.DisplayHandle` to __update__."""

        TraitletOutput.update(change["new"])

    stack = traitlets.List()

    def __enter__(TraitletOutput):
        """`TraitletOutput.__enter__` changes the context of how display objects are published using `IPython.utils.capture`."""

        object = IPython.utils.capture.capture_output()
        """We use a stack just in case..."""

        TraitletOutput.stack.append((object, object.__enter__()))

    def __exit__(TraitletOutput, *e):
        """`TraitletOutput.__exit__` the `TraitletOutput.stack` and `TraitletOutput.update` any existing displays."""

        capturer, captured = TraitletOutput.stack.pop()
        capturer.__exit__(*e)
        outputs = captured.outputs and captured.outputs[0].data or {"text/plain": captured.stdout}
        TraitletOutput.update(outputs, raw=True)

    def __init__(TraitletOutput, *args, **kwargs):
        IPython.display.DisplayHandle.__init__(TraitletOutput)
        Output.__init__(TraitletOutput, *args, **kwargs)


class Handler(traitlets.HasTraits):
    """`Handler` is a `traitlets` `object` that manager state between itself and the `Handler.parent`.
>>> handler = Handler(foo=2)
>>> handler
<...Handler...>"""

    parent = traitlets.Instance(
        IPython.InteractiveShell,
        help="""`Handler.parent` is a shell who's namespace is evented with the `Handler`.
                               >>> handler.parent
                               <...Shell...>""",
    )
    children = traitlets.Tuple(help="""`Handler.children` holds the widgets for the `Handler`""")
    display = traitlets.Dict(
        help="""`Handler.display` is a keyed version of the `Handler.children`.
                            >>> assert handler.children == tuple(handler.display.values())"""
    )
    wait = traitlets.Bool(False)
    display_cls = traitlets.Type(
        TraitletOutput, help=""">>> assert issubclass(handler.display_cls, TraitletOutput)"""
    )
    callable = traitlets.Any()
    globals = traitlets.Dict()
    locals = traitlets.Dict()

    def __init__(App, *globals, wait=False, parent=None, **locals):
        func = locals.pop("callable", None)
        parent = parent or IPython.get_ipython()
        globals = {
            str: parent.user_ns.get(str, None)
            for str in map(str.strip, itertools.chain(*map(str.split, globals)))
            if str not in locals
        }
        locals.update(
            {
                k: locals.get(k, None) or value
                for k, value in getattr(App, "__annotations__", {}).items()
            }
        )
        super().__init__(parent=parent, wait=wait, callable=func, locals=locals, globals=globals)
        App.wait or App.parent.events.register("post_execute", App.user_ns_handler)

        if not App.callable and callable(App):
            App.callable = lambda _: App()

        for alias, dict in zip("globals locals".split(), (App.globals, App.locals)):
            for name, object in dict.items():
                App.display[name] = widget = App.widget_from_abbrev(name, object)
                App.children += (widget,)
                if "value" in widget.traits():
                    App.add_traits(**{name: type(widget.traits()["value"])(widget.value)})
                    if App.wait:
                        App.wait_handler
                    else:
                        traitlets.link((widget, "value"), (App, name))
                if name in App.globals:
                    App.observe(App.globals_handler, name)

        if App.callable:
            App.children += (App.display_cls(description="result", value=App.callable(App)),)
            App.observe(App.call)

    def user_ns_handler(App, *args):
        with pandas_ambiguity():
            [
                str in App.parent.user_ns and setattr(App, str, App.parent.user_ns[str])
                for str in App.globals
            ]

    def globals_handler(App, change):
        if change["type"] == "change":
            App.parent.user_ns[change["name"]] = change["new"]

    def call(App, change):
        with pandas_ambiguity(), App.children[-1]:
            value = App.callable(App)
            IPython.display.display(value)

    def wait_handler(App, change):
        ...

    def widget_from_abbrev(App, name, object):
        return App.display_cls(description=name, value=object)

    def __enter__(App):
        return App

    def __exit__(App, *e):
        for children in App.children[0]:
            [hasattr(child, "value") and child.unobserve("value") for child in children]
        App.unobserve(None), App.wait or App.parent.events.unregister(
            "post_execute", App.user_ns_handler
        )

    def _ipython_display_(App):
        [object.display(object) for object in App.children]


@contextlib.contextmanager
def pandas_ambiguity(nz=None):
    pandas = sys.modules.get("pandas", None)
    if pandas:
        pandas.Series.__bool__ = pandas.DataFrame.__bool__ = lambda df: True
        yield
        try:
            del pandas.DataFrame.__bool__, pandas.Series.__bool__
        except:
            ...
    else:
        yield


@IPython.core.magic.magics_class
class Magic(IPython.core.magic.Magics):
    """>>> %ypp foo
<...App...>
>>> %%ypp
...        print(foo)
WidgetOutput(...Output...)"""

    @IPython.core.magic.line_magic("ypp")
    def line(self, line):
        return App(line)

    @IPython.core.magic.cell_magic("ypp")
    def cell(self, line, cell):
        app, object = App(line), (ipywidgets and WidgetOutput or TraitletOutput)()
        self.update(cell, object, {}),
        app.observe(functools.partial(self.update, cell, object), line.split())
        return object

    def update(self, cell, object, change):
        with object:
            IPython.get_ipython().run_cell(cell)


if ipywidgets:

    class WidgetOutput(ipywidgets.Accordion, Output):
        output = traitlets.Instance(ipywidgets.Output)

        def __init__(WidgetOutput, *args, **kwargs):
            kwargs["output"] = kwargs.get("output", ipywidgets.Output())
            super().__init__(*args, **kwargs)
            WidgetOutput.children += (WidgetOutput.output,)
            WidgetOutput._titles = {0: WidgetOutput.description}
            WidgetOutput.observe(WidgetOutput.update, "value")
            WidgetOutput.update({"new": WidgetOutput.value})

        @traitlets.observe("selected_index")
        def _change_index(WidgetOutput, change):
            if WidgetOutput.selected_index is None:
                WidgetOutput._titles = {
                    0: f"""{WidgetOutput.description} of type {type(WidgetOutput.value)}"""
                }
            else:
                WidgetOutput._titles = {0: WidgetOutput.description}

        def __enter__(WidgetOutput):
            WidgetOutput.output.clear_output(True)
            WidgetOutput.output.__enter__()

        def __exit__(WidgetOutput, *e):
            WidgetOutput.output.__exit__(*e)

        def update(WidgetOutput, change):
            with WidgetOutput:
                IPython.display.display(change["new"])

            if not WidgetOutput.selected_index:
                WidgetOutput._change_index({"new": None})

    w = WidgetOutput(value=range, description="Test")


if ipywidgets:

    class App(Handler):
        container = traitlets.Instance(ipywidgets.VBox)
        display_cls = traitlets.Type(WidgetOutput)

        _ = traitlets.default("container")(lambda x: ipywidgets.VBox())

        def __init__(App, *args, **kwargs):
            super().__init__(*args, **kwargs)
            children = []
            for alias, dict in zip("globals locals".split(), (App.globals, App.locals)):
                if dict:
                    children.append(
                        ipywidgets.Accordion(
                            children=[ipywidgets.VBox(layout={"display": "flex"})],
                            _titles={0: alias},
                        )
                    )
                    for name, object in dict.items():
                        children[-1].children[0].children += (App.display[name],)
            App.container.children = tuple(children)

            if App.callable:
                App.container.children += (App.children[-1],)

        def widget_from_abbrev(App, name, object, *, widget=None):
            annotation = {
                **App.parent.user_ns.get("__annotations__", {}),
                **getattr(App, "__annotations__", {}),
            }.get(name, object)
            if "pandas" in sys.modules and isinstance(object, sys.modules["pandas"].DataFrame):
                ...
            elif isinstance(annotation, list):
                widget = ipywidgets.SelectMultiple(options=tuple(annotation), value=object)
            elif isinstance(annotation, ipywidgets.Widget):
                widget = annotation
            else:
                widget = ipywidgets.interactive.widget_from_abbrev(
                    annotation, App.locals.get(name, App.parent.user_ns.get(name, object))
                )
            widget = widget or WidgetOutput(description=name, value=object)
            widget.description = name
            return widget

        def _ipython_display_(App):
            IPython.display.display(App.container)


try:
    import ipywxyz

    class WXYZ(App):
        container = traitlets.Instance(ipywxyz.DockBox)
        _ = traitlets.default("container")(lambda x: ipywxyz.DockBox(layout={"height": "20vh"}))

        def __init__(App, *args, **kwargs):
            App.container.children = Handler.__init__(App, *args, **kwargs) or App.children


except:
    ...


def load_ipython_extension(shell):
    shell.register_magics(Magic)


def unload_ipython_extension(shell):
    ...


if __name__ == "__main__":
    import pidgin, nbconvert

    display = IPython.display.display
    with open("ypp.py", "w") as f:
        f.write(
            __import__("black").format_str(
                nbconvert.PythonExporter(
                    config={"TemplateExporter": {"exclude_input_prompt": True}},
                    preprocessors=[pidgin.publishing.TanglePreProcessor()],
                ).from_filename("ypp.md.ipynb")[0],
                100,
            )
        )
        if 0:
            with IPython.utils.capture.capture_output():
                get_ipython().system("pyreverse --show-builtin  --module-names=y -osvg -b ypp ")
        display(IPython.display.SVG("classes.svg"))
        get_ipython().system("isort ypp.py")
    if 10:
        get_ipython().system("pyflakes ypp.py")
