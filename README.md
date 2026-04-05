# 🐮 moo (moolang)

*No configuration files! Only your code and the MOO-NOLITH.*

This project was created because I think three contradictory things
hold true: monoliths are lightweight,
separation of concerns is great,
and splitting configuration from code is pesky.

Thus you can use *moo*; a tiny build system that inlines
external configurations. It also allows packaging
components into one file to avoid tens of API calls
for loading a web page or platform-dependent macros.

Some of the things you can do:

- Create base64 images encodings and embed them in web pages.
- Declare a virtual environment for your Python project within its main file and "run" that file without setup.
- Create a list of your favorite command line instruction in one file to call.
- Declare a build process within C code.
- Create programming language macros that make use of complicated system calls.

**Requirements:** Python 3.11 or later (no virtual environment or dependencies needed)<br>
**Author:** Emmanouil Krasanakis (maniospas@hotmail.com)<br>
**License:** Apache 2.0 for `moo.cpp`, individual licenses for third-party files in `std/`<br>

## 📋 Changelog

## MOO - nightly build 

Will culminate into the next version

- 


### MOO - 0.6 (31 March 2026)
- Fast C++ implementation
- Base64 and OS functionality without needing scripts.

### MOO - 0.5 (28 March 2026)
- Loops
- Conditions
- Patterns
- Renamed *const* to *str*

### MOO - 0.4 (26 March 2026)
- First stable core (changelog starts tracking from hereon)
- Test suit

## 🚀 Quickstart

Download an executable from the latest release, or clone this repository and 
run `g++ moo.cpp -o moo -Wall -O3` to produce that executable.

You can also install the *moolang* VSCODE extension to highlight *moo* files.
Alternate between the programming language in which you embed instructions and
*moo* highlighting.

Instructions are placed within your text or code.
Below is an example, where `/*** code ***/` inlines that code.
Use `/**/ code` for inlining that ends at the end of the current line
(and skips the new line character). Do note that this creates an error
because `user` is not declared anywhere yet.

```c
// hello.linux.txt.moo
Hello /*** user ***/ from a linux file!
```

Inlined expressions either have the form `varname` to evaluate
to a variable `varname = F text` or `F text`, where `F` is one
of the builtin functions. Before running, nested
`{expressions}` are evaluated first.
Variable names can contain dots. Here is a quick peek
of these concepts:

```c
// hello.txt.moo
Hi!
/**/ moo.safe += pattern {moo.python} scripts/ *
/**/ os = system {moo.python} scripts/os.py
/**/ user = str maniospas
/**/ import hello.{os}.txt.moo
- Be safe out there.
```

Some basic concepts are demonstrated above:
- `+=` adds some data to a list of values. In this case, `moo.safe` determines allowed system command prefixes. More on lists and safety later.
- `system` runs a system command and captures its console output. These are scheduled as parallel processes, cached, and execute lazily. If you want to forcefully synchronize them, use `pass {variable}` to force them to evaluate and then be ignored.
- `str` acknowledges the rest of the text as a constant string value.
- `import` inlines another file. Imported files can access and shadow the variables of their callers.

Now, when built on the linux platform with *python3 moo.py hello.txt.moo* the
following file is produced by removing the *.moo* extension:

```c
// hello.txt
Hi!

Hello world from a linux file!
- Be safe out there.
```

## ⚡ Documentation

Find language documentation [here](https://moolang.netlify.app/).
