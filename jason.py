#!/usr/bin/env python
# coding: utf-8

import collections, abc, io, IPython, functools

__all__ = (
    "Jay",
    "J",
    "Json",
    "D",
    "Dict",
    "L",
    "List",
    "S",
    "String",
    "Csv",
    "Context",
    "Schema",
    "Patch",
    "T",
    "Toml",
    "Y",
    "Yaml",
)
if __name__ == "__main__":
    get_ipython = IPython.get_ipython


get_data = lambda x: get_data(x.data) if hasattr(x, "data") else x


list_types = list, collections.UserList
str_types = str, collections.UserString
dict_types = dict, collections.UserDict


class Stype(abc.ABCMeta):
    """Base class for short shortened string formatters."""

    def __mod__(Stype, str):
        return Jay.load(Stype.load(str))

    format = __call__ = __mod__


class Jay(metaclass=Stype):
    def load(object):
        object = get_data(object)
        if isinstance(object, (dict, collections.UserDict)):
            return D(object)
        if isinstance(object, (list, collections.UserList)):
            return L(object)
        if isinstance(object, (str, collections.UserString)):
            return S(object)
        return object


J = Jay


class Json(metaclass=Stype):
    """>>> Json%'{"a": "b"}'
{'a': 'b'}
"""

    load = __import__("json").loads


class Csv(metaclass=Stype):
    """>>> Csv('''a, b, c
... 1, 2, 3''')
[['a', ' b', ' c'], ['1', ' 2', ' 3']]
"""

    def load(object, *, delimiter=","):
        import csv

        if isinstance(object, tuple):
            delimiter, object = object
        return L(list(csv.reader(io.StringIO(object), delimiter=delimiter)))


class Img(metaclass=Stype):
    def load(str):
        return __import__("pytesseract").image_to_string(
            __import__("PIL").Image.open(str)
        )


def cfg(str):
    parser = __import__("configparser").ConfigParser()
    parser.read_string(str)
    return {section: dict(parser[section]) for section in parser.sections()}


class Cfg(metaclass=Stype):
    """>>> Cfg%'[header]\\na: b'
{'header': {'a': 'b'}}
"""

    load = cfg


class Object:
    def __getitem__(O, object):
        if isinstance(object, str) and object.startswith("/"):
            return Jay(__import__("jsonpointer").resolve_pointer(O.data, object))
        return super().__getitem__(object)

    def __add__(O, object, *, op="add"):
        if not isinstance(object, Patch):
            object = Patch(
                [
                    {
                        "op": op,
                        "path": key,
                        **({} if op == "replace" else {"value": value}),
                    }
                    for key, value in (
                        object.items()
                        if isinstance(object, dict)
                        else zip(object, [""] * len(object))
                    )
                ]
            )
        return object(O.data)

    __floordiv__ = functools.partialmethod(__add__, op="replace")

    __sub__ = functools.partialmethod(__add__, op="remove")

    def __or__(O, object):
        return __import__("jsondiff").diff(O.data, object)

    def __and__(O, object):
        O.update({"@context": object})
        return O

    __truediv__ = __floordiv__

    def __matmul__(O, object):
        return Context(object) @ O.data

    def __mod__(O, object):
        return Context(object) % O.data

    def __call__(O, object):
        return Schema(object)(O.data)

    def __setitem__(J, path, value):
        if path.startswith("/"):
            return J + {path: value}
        return super().__setitem__(path, value)

    def __wrapped__(O):
        raise AttributeError("__wrapped__")

    def __pos__(O):
        data = dict(O.data)
        return Context(data.pop("@context")) @ data

    def __neg__(O):
        data = dict(O.data)
        return Context(data.pop("@context")) % data


O = Object


class String(O, collections.UserString):
    """>>> s = S("foo")
>>> type(s) # doctest: +ELLIPSIS
<...S...>

>>> s["/1"]
'o'

"""


S = String


class List(O, collections.UserList):
    """>>> l = L(['a', 'foo'])
>>> type(l) # doctest: +ELLIPSIS
<...L...>
>>> l['/0']
'a'
>>> l['/1/1']
'o'
>>> l + {'/2': 3}
['a', 'foo', 3]

>>> L([1,2]) | [1]
{delete: [1]}
>>> L([1,2])-{'/1'}
[1]
"""


L = List


class Patch(__import__("jsonpatch").JsonPatch, L):
    """>>> l = L(['a', 'foo'])
>>> type(l) # doctest: +ELLIPSIS
<...L...>
>>> l['/0']
'a'
>>> l['/1/1']
'o'
"""

    def __call__(Patch, object):
        return Jay(Patch.apply(object))

    @property
    def data(Patch):
        return Patch.patch


class Dict(O, collections.UserDict):
    """>>> d = Json%'{"a": [1, {"b": ["foo", 3, "bar"]}]}'
>>> d
{'a': [1, {'b': ['foo', 3, 'bar']}]}
>>> d += {'/c': ['baz', None]}
>>> d
{'a': [1, {'b': ['foo', 3, 'bar']}], 'c': ['baz', None]}
>>> d - {'/a', '/c/1'}
{'c': ['baz']}
>>> (d + {'/g': 'testing'}) @ {'g': 'https://foo'}
[{'https://foo': [{'@value': 'testing'}]}]
>>> d = (d + {'/g': 'testing'}) & {'g': 'https://foo'}
>>> +d
[{'https://foo': [{'@value': 'testing'}]}]
"""

    def __deepcopy__(D, state):
        return type(D)(D.data)


D = Dict


class Schema(D):
    """>>> Schema({'type': 'string'})('asdf')
'asdf'

>>> with __import__('pytest').raises(__import__('jsonschema').ValidationError): 
...     Schema({'type': 'string'})(1)
"""

    def __call__(Schema, object):
        __import__("jsonschema").validate(object, Schema.data)
        return object


class Context(D):
    """>>> context = Context({"gh": "https://github.com"})
>>> context@'gh'
'https://github.com'
>>> context@{'gh': 'deathbeds'}
[{'https://github.com': [{'@value': 'deathbeds'}]}]
"""

    def __mod__(Context, object):
        return D(__import__("pyld").jsonld.compact(object, Context.data))

    def __matmul__(Context, object):
        if isinstance(object, str):
            return Context.expand(object, Context.data)
        object.update({"@context": Context.data.get("@context", Context.data)})
        return L(__import__("pyld").jsonld.expand(object))

    __call__ = __matmul__

    @staticmethod
    def expand(str, ctx):
        """>>> Context.expand("gh", {"gh": "https://github.com"})
'https://github.com'
>>> Context.expand('q', {})
'q'
"""
        object = __import__("pyld").jsonld.expand({str: "", "@context": ctx})
        if object:
            return next(iter(object[0]))
        return str


class Yaml(metaclass=Stype):
    """>>> Y%'[a, b]'
['a', 'b']
>>> Y%'{a: b}'       
{'a': 'b'}
"""

    def load(str):
        import ruamel.yaml

        return ruamel.yaml.load(io.StringIO(str), Loader=ruamel.yaml.Loader)


Y = Yaml


class Toml(metaclass=Stype):
    """>>> T%'title = "TOML Example"'
{'title': 'TOML Example'}
"""

    def load(str):
        return __import__("toml").loads(str)


T = Toml


if __name__ == "__main__":
    import pidgin, nbconvert, black, IPython

    display = IPython.display.display
    with open("jason.py", "w") as f:
        f.write(
            black.format_str(
                nbconvert.PythonExporter(
                    config={"TemplateExporter": {"exclude_input_prompt": True}},
                    preprocessors=[pidgin.publishing.TanglePreProcessor()],
                ).from_filename("jason.ipynb")[0],
                mode=black.FileMode(),
            )
        )
        if 0:
            with IPython.utils.capture.capture_output(stderr=False, stdout=False):
                get_ipython().system(
                    "pyreverse --show-builtin  --module-names=y -osvg jason "
                )
        display(IPython.display.SVG("classes.svg"))
        with IPython.utils.capture.capture_output():
            get_ipython().system("isort jason.py")
    if 10:
        get_ipython().system("pyflakes jason.py")
    __import__("doctest").testmod()

# https://mybinder.org/v2/gh/deathbeds/ypp/a4c56e9a3a761b32cb3c9d5b630f22f4a216dd67?filepath=examples.ipynb
