# 🐮 moolang 

*A build system to embed in your other code. There are no configuration files! Only your code and THE MOO-NOLITH.*

This project was created because monoliths are lightweight.
But separation of concerns is also great. Thus you can use *moo*; a 
tiny build system for packaging components into a monolith (or several monoliths for very large projects)
and avoid stuff like tens of API calls for loading a web page or platform-dependent compilation macros. 

*Moo* also allows conditional builds and interaction with the build
environment. Yet there are no external configuration files that make me feel stuffed; 
everything is inlined in your code.

**Requirements:** Python 3.11 or later (no virtual environment or dependencies needed)<br>
**Author:** Emmanouil Krasanakis (maniospas@hotmail.com)<br>
**License:** Apache 2.0

## 🚀 Quickstart

Install Python 3.11 or later and download *moo.py*. You can optionally get some useful *scripts/* too.

You can also install the *moolang* VSCODE extension to highlight *moo* files. You can alternate between
your programming language and *moo* highlighting.

Declare the building process within your text or code.
The end-goal is to create one file (THE MOO-NOLITH)
that packs in everything about your project. This could even be
a large C file with platform-conditioned compilation resolved 
(you can also use *moo* as a more powerful yet safer replacement of
the macro system), an html with embedded fonts and images as base64
encoding, and so on.

Here's an example, where `/*** code ***/` embeds 
*moo* code, like variables and expressions. You may use
`/**/ code` for code that ends at end of line; 
the last case skips the line break.

```c
// hello.linux.txt.moo
Hello /*** user ***/ from a linux file!
```

You can use `{nested code}` to evaluate nested *moo*
code first. Expressions either have the form `varname = F text` 
or `F text`, where `F` is one of the builtin functions. 
Assignments do not propagate the value.

```c
// hello.txt.moo
Hi!
/**/ moo.safe += const {moo.python} scripts/
/**/ os = system {moo.python} scripts/os.py
/**/ user = const maniospas
/**/ import hello.{os}.txt.moo
- Be safe out there.
```

The builtins shown above are:
- `+=` adds some data to a list of values. In this case, `moo.safe` determines allowed system command prefixes. More on lists and safety later.
- `system` runs a system command and captures its console output. These are scheduled as parallel processes, cached, and execute lazily. If you want to forcefully synchronize them, use `pass {variable}` to force them to evaluate and then be ignored.
- `const` acknowledges the rest of the text as a constant value
- `import` inlines another file. Imported files can access and shadow the variables of their callers.

Now, when built on the linux platform with *python3 moo.py hello.txt.moo* the
following file is produced by removing the *.in* extension:

```c
// hello.txt
Hi!

Hello world from a linux file!
- Be safe out there.
```


## ⚡ About

*While* moo *is under development, here are some basic concepts.*

**Variables** are immutable and inherited from where your code is included. But you can locally shadow external names. Variable names are independent of the rest of your file.

**Regions** are essentially lists of values that can be viewed as one huge string with a given separator between its segments. 
For example, you may have separate regions for your html style, script, and body. Declare a region like below, and append text to it. Regions are empty by default.

```c
/**/ BODY = region {moo.symbols.line}
/**/ BODY += this will show in the body
<body>/***BODY***/</body>
```

**Placeholders** are means of not evaluating a region (only a region!) immediately but at the latest possible moment to let it accrue more content.Usually that place is the end of the file, but placeholders are also re-evaluated for the inputs of `do` statements. Here is an example:

```c
/**/ x = region {moo.symbols.line}
/**/ placeholder x
This is something placed after the placeholder.
/**/ x += const This is placed at the beginning.
```

**Scripts.** In addition to *moo.py*, which is a self-contained implementation for running the language without any dependencies or virtual environment, you can also get a collection of pre-installed scripts that leverage Python's impressive standard library. You can reference the python executable with the `{moo.python}` variable in your commands.

Some of available scripts (the list is growing) are:

- *scripts/os.py* tells you the operating system currently running. This often helps tailor to the local environment.

- *scripts/b64.py* converts a file to base64 encoding.

**Safety.** In general, use `command` to run specific external commands. The `moo.safe` variable determines how the command
can be prefixed. A common default is `/*** append moo.safe {moo.python} scripts/ ***/` for allowing all contents of the *scripts/* folder
to be called by Python while preventing all other programs AND Python from being executed with code injection attacks. The assumption
is that you trust whitelisted commands and folder combinations.

You can try to append to the safety list from anywhere, but this action will
be rejected unless the ENTRANT FILE allows a superset of permissions. This is done to achieve safety. Also `..` is not allowed
within commands, so as to prevent escaping from the safety mechanism. If you want to use it, also use 
path resolution everywhere to convert relative paths to absolute ones.

**For now, `do` and `eval` remain unsafe.**

**Reuse** moo code that is packed into `const` data like below. The `do` statement works by replacing nested
statements with their expanded version and *then* properly interpreting the result. Interpretation occurs once only. 
Under this pattern, the `const` declaration works like a capturing lambda expression as it resolves
all its `{}` segments at the time of declaration. So, below we get to call the b64 Python script from with an 
appropriate argument. UYou can declare such helpers at the top level and have them be
shared in imported *moo* files.

```c
/**/ append moosafe {moo.python} scripts/
/**/ b64 = const system {moo.python} scripts/b64.py
/**/ b64
/**/ do {b64} examples/file1.txt.moo
```

This will create a file like the following (the middle b64 is used to demonstrate the exact command):

```txt
system /usr/bin/python3 scripts/b64.py
LyoqKiB1c2VyID0gY29uc3Qgd29ybGQqKiovCi8qKiogZmlsZSA9IGltcG9ydCBleGFtcGxlL2Zp
bGUyLntjb21tYW5kIHtweXRob259IHNjcmlwdHMvb3MucHl9LnR4dC5tb28gKioqLwovKioqIEJP
RFkgPSByZWdpb24qKiovCi8qKiogYXBwZW5kIEJPRFkge2ZpbGV9ICoqKi8KCjxib2R5Pi8qKiog
Qk9EWSAqKiovPC9ib2R5PgoK
```

**Namespaces** are also there to compartmenize and enable/disable parts of files.
To work within a namespace, prefix your instruction with `NAME:`, where *NAME* is its name.
You can access all namespaces declared in the same file from within each other, 
but *not* namespaces declared in other files, even if those files import the current one.
What you *can* do is call another file within a namespace to adjust what information is passed 
and return without polluting your *moo* code.
The following example demonstrates usage of a namespace, alongside a list of final features:

- `enabled` checks for a True or False value and correspondingly disables all future uses of the
namespace in the file. Do note that namespaces in other files remain unaffected, even if they 
have the same name. You can *not* re-enable a disabled namespace later.
- `eval` evaluates a subsequent Python expression
- `mooargs` is a string representation of additional arguments passed to the script.
- `schedule` runs a system command after the monolith is created. Scheduled tasks run concurrently.

Thus, if you run the following per `python3 moo.py src/main.c.moo --compile` it will compile the program.
Do note the usage of `///**/` as a pattern that allows *moo* to appear commented by C tools but also evaluates
to valid code when replaced with anything.


```c
// src/main.c.moo
///**/ COMPILE: moo.safe += gcc
///**/ COMPILE: enabled {eval "--compile" in {mooargs}}
///**/ COMPILE: schedule gcc -Wall -O3 -o lettuce src/main.c

#include <stdio.h>

int main() {
    printf("Hello world!\n");
    return 0;
}
```

**Error messages.** If something goes wrong, *moo* will create a stack trace
of its failed attempt. Do note that that lines and columns refer to the start
of *moo* blocks within your code. However, there is proper denotation of
the exact point of failure, even within nested {} blocks or expanded expressions. 
If system commands fail due to lazy execution,
their initial declaration is pointed out. Here is an example.

![examples/example_error.png](examples/example_error.png)

