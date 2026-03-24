import sys, base64, subprocess, tempfile, atexit, re
from pathlib import Path
from typing import Any, Callable
RED, GREEN, CYAN, YELLOW, RESET = "\x1b[31m", "\x1b[32m", "\x1b[36m", "\x1b[33m","\x1b[0m"

class Region:
    def __init__(self, sep="\n"):
        self.contents = list()
        self.sep = sep
    
    def push(self, contents):
        self.contents.append(contents)
    
    def __str__(self):
        return "\n".join(self.contents) if self.contents else ""

    def permits(self, value):
        for contents in self.contents:
            if value.startswith(contents): return True
        return False

class Command:
    def __init__(self, expression, error_callback=None):
        self.expression = expression
        self.cached = None
        self.error_callback = error_callback
        self.proc = subprocess.Popen(expression, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
    def __str__(self):
        if self.cached is not None: return self.cached
        stdout, stderr = self.proc.communicate()
        if self.proc.returncode:
            message = f"non-zero exit code {self.proc.returncode}\n{stderr}"
            if self.error_callback: self.error_callback(message)
            raise Exception(message)
        self.cached = str(stdout)
        return self.cached


class Context:
    def __init__(self, path="<inline>", parent=None, shared_namespaces=False):
        self.path = path
        self.parent = parent
        self.row = 0
        self.col = 0
        self.vars = dict()
        self.namespaces = dict()
        self.enabled = True
        self.shared_namespaces = shared_namespaces
        self.tokens = list()
        self.token_pos = 0

    def update(self, row, col):
        self.row = row
        self.col = col

    def get_existing_namespace(self, name: str):
        namespace = self.namespaces.get(name, None)
        if namespace is None and self.parent and self.shared_namespaces: return self.parent.get_existing_namespace(name)
        return namespace

    def get_namespace(self, name: str):
        namespace = self.namespaces.get(name, None)
        if namespace is None and self.parent and self.shared_namespaces: namespace = self.parent.get_existing_namespace(name)
        if namespace is not None: return namespace
        namespace = Context(path=self.path+"/"+name, parent=self, shared_namespaces=True)
        namespace.update(self.row, self.col)
        self.namespaces[name] = namespace
        return namespace

    def __setitem__(self, name: str, value: str|Region|Command):
        existing = self.vars.get(name, None)
        if existing: 
            assert isinstance(existing, Region), "Can append but not reassign to region: "+name
            assert isinstance(value, Command)==isinstance(existing, Command), "Conflicting variable type (command vs const): "+name
            if not isinstance(value, Command): assert value == existing, "Cannot overwrite previously different variable: "+name
            else: assert value.expression == existing.expression, "Cannot overwrite previously different variable: "+name
            return
        self.vars[name] = value
    
    def get_raw_item(self, name: str):
        existing = self.vars.get(name, None)
        if existing is None and self.parent: return self.parent.get_raw_item(name)
        return existing

    def __getitem__(self, name: str):
        existing = self.vars.get(name, None)
        if existing is None and self.parent: return self.parent[name]
        assert existing is not None, "Variable not found: "+name
        return str(existing)

class Globals:
    def __init__(self, log_enabled=True):
        self.imported = dict()
        self.commands = dict()
        self.temp_counter = 0
        self.log_enabled = log_enabled
        self.schedule = list()

    def command(self, expression, context: Context=None):
        self.log("  system", expression)
        existing = self.commands.get(expression, None)
        if existing: return existing
        existing = Command(expression, error_callback=lambda message: self.error(message, context=context))
        self.commands[expression] = existing
        return existing
    
    def create_temp(self):
        self.temp_counter += 1
        return "__"+str(temp_counter)

    def log(self, kind: str, message: str, color=CYAN):
        if self.log_enabled: print(color+kind+RESET, message, file=sys.stderr)

    def error(self, message: str, context: Context=None):
        print(RED+"error"+RESET, message, file=sys.stderr)
        while context is not None:
            print(RED, " in", CYAN+context.path+RESET, "line", context.row+1, "column", context.col+1, file=sys.stderr)
            if context.tokens:
                toks = context.tokens
                i = context.token_pos
                start = i
                first_tok = ""
                end_tok = ""
                while start > 0:
                    if "\n" in toks[start - 1]:
                        first_tok = toks[start - 1].split("\n")[-1]
                        break
                    start -= 1
                end = i
                while end < len(toks):
                    if "\n" in toks[end]:
                        last_tok = toks[end].split("\n", 1)[0]
                    end += 1
                snippet = first_tok+"".join(toks[start:end])+end_tok
                offset = sum(len(t) for t in toks[start:i])+len(first_tok)
                print(RED + "  └─ " + RESET + snippet, file=sys.stderr)
                print(RED + "     " + " "*offset + "^"*len(toks[i])+RESET, file=sys.stderr)
            context = context.parent
        sys.exit(1)

def extract_arg(args, name):
    if name not in args: return False
    args.remove(name)
    return True

def consume_block(globs: Globals, tokens: list[str], context: Context, pos:int, num_tokens: int, variable_expansion_only=False):
    ret = ""
    while pos<num_tokens:
        token = tokens[pos]
        if token=="{":
            if variable_expansion_only: 
                if pos<num_tokens-2 and tokens[pos+1]!="{" and tokens[pos+2] == "}":
                    returned = context[tokens[pos+1]] 
                    pos += 3
                    ret += str(returned)
                    continue
                ret += token
                pos += 1
                continue
            start = pos
            depth = 0
            while pos<num_tokens:
                if tokens[pos]=="{": depth+=1
                elif tokens[pos]=="}": 
                    depth -= 1
                    if depth == 0:
                        returned, pos = parse_block(globs, tokens, context, start+1, pos)
                        ret += str(returned)
                        break
                pos += 1
        else: 
            ret += token
            pos += 1
    return ret, pos

def parse_block(globs: Globals, block: str|list[str], context: Context, pos:int=0, num_tokens:int=None):
    try:
        if isinstance(block, list): tokens = block
        else:
            block = block.replace("\n", " ").strip()
            raw_parts = re.split(r'(\s+|:|\\+|=|[{}])', block)
            tokens = [p for p in raw_parts if p != ""]
        if num_tokens is None: num_tokens = len(tokens)
        assert pos<num_tokens, "empty block"
        context.tokens = tokens
        if pos==num_tokens-1:
            context.token_pos = pos
            return context[tokens[pos]], num_tokens+1
        returned = ""
        while pos<num_tokens:
            context.token_pos = pos
            token = tokens[pos]
            if token.isspace(): 
                pos += 1
                continue
            while pos<num_tokens-1 and tokens[pos+1].isspace(): 
                pos += 1
            if pos<num_tokens-2 and tokens[pos+1]==":":
                namespace = context.get_namespace(token)
                if not namespace.enabled:
                    pos = num_tokens
                    continue
                pos += 2
                while pos<num_tokens and tokens[pos].isspace(): 
                    pos += 1
                returned, pos = parse_block(globs, block, namespace, pos, num_tokens)
                assert pos>=num_tokens-1, "leftover code after namespace ends"
            elif pos<num_tokens-2 and tokens[pos+1]=="=":
                assert token!="moosafe", "the moosafe region cannot be shadowed because it holds permissions"
                returned, pos = parse_block(globs, block, context, pos+2, num_tokens)
                context[token] = returned
                returned = ""
                assert pos>=num_tokens-1, "leftover code after assignment"
            elif token=="enabled":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                if returned=="False": 
                    context.enabled = False
                    globs.log("disabled", context.path, color=YELLOW)
                elif returned!="True": 
                    globs.error("enabled can only be True or False but got: "+returned+"\nDid you forget the {}?", context)
                returned = ""
            elif token=="path":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = str(Path(str(returned)).resolve())
            elif token=="eval":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = eval(returned)
                returned = str(returned)
            elif token=="system":
                prev_pos = context.token_pos
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = str(returned)
                moosafe = context.get_raw_item("moosafe")
                context.token_pos = prev_pos
                assert ".." not in returned, ".. cannot be part of commands, as they could escape the safety sandbox: "+returned+"\nPerhaps use the path command to turn relative paths to absolute ones."
                assert moosafe.permits(returned), "moosafe does not permit command: "+returned+"\nConsider appending its prefix to the moosafe variable. Example: append moosafe {python} to allow python execution"
                returned = globs.command(returned, context=context)
            elif token=="import":
                prev_pos = context.token_pos
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                context.token_pos = prev_pos
                returned = load_file(globs, returned, context)
            elif token=="const":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
            elif token=="pass":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = ""
            elif token=="schedule":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                globs.schedule.append(str(returned))
                returned = ""
            elif pos<num_tokens-2 and tokens[pos+1]=="+":
                pos += 2
                assert tokens[pos]=="=", "+ is not a valid operator. Perhaps you meant += but it was followed by: "+tokens[pos]
                varname = token
                var = context.get_raw_item(varname)
                assert var is not None, "cannot find variable: "+varname
                assert isinstance(var, Region), "can apply += to regions: "+varname
                while pos<num_tokens-1 and tokens[pos+1].isspace(): 
                    pos += 1
                returned, pos = parse_block(globs, tokens, context, pos+1, num_tokens)
                returned = str(returned)
                if varname=="moosafe": 
                    assert not context.parent.parent or var.permits(returned), "the moosafe region can only be edited from the main context but a dependent file tried to append contents that do not already exist: "+returned
                var.push(returned)
                returned = ""
            elif token=="region":
                pos += 1
                returned = Region()
                assert pos>=num_tokens-1, "leftover code after declaring region"
            elif token=="do":
                prev_pos = context.token_pos
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens, variable_expansion_only=True)
                new_raw_parts = re.split(r'(\s+|:|\\+|=|[{}])', returned.replace("\n", " ").strip())
                new_tokens = [p for p in new_raw_parts if p != ""]+tokens[pos+1:num_tokens]
                context.token_pos = prev_pos
                returned, _ = parse_block(globs, new_tokens, context)
            elif token=="{": raise Exception("cannot start a {} block here\n      Expecting a function or variable name.\n      Perhaps you meant to preface it with `do` or `const`?")
            else: raise Exception("unknown function: "+token+"\n      Perhaps you meant to preface it with `const`?")
            pos += 1
        return returned, pos
    except Exception as e:
        globs.error(str(e), context)
    except AssertionError as e:
        globs.error(str(e), context)


def load_file(globs: Globals, path: str, parent_context: Context=None):
    context = Context(path, parent=parent_context)
    globs.log("  import", path)
    has_started = 0
    block = ""
    new_contents = ""
    end_at_end_line = False
    with open(path) as file:
        for line_num, line in enumerate(file):
            line_length = len(line)
            col_num = 0
            while col_num<line_length:
                if (col_num<=line_length-4 and line[col_num:col_num+4]=="***/" and not end_at_end_line) or (end_at_end_line and (line[col_num]=="\n" or col_num==line_length-1) ):
                    if end_at_end_line and col_num == col_num==line_length-1 and line[col_num]!="\n": 
                        block += line[col_num]
                    has_started -= 1
                    if not has_started:
                        col_num += 1 if end_at_end_line else 4
                        returned = parse_block(globs, block, context)
                        new_contents += str(returned[0])
                        block = ""
                        end_at_end_line = False
                        continue
                if col_num<=line_length-4 and ((line[col_num:col_num+4]=="/***" and not end_at_end_line) or line[col_num:col_num+4]=="/**/"):
                    has_started += 1
                    if has_started==1:
                        context.update(line_num, col_num)
                        end_at_end_line = line[col_num:col_num+4]=="/**/"
                        col_num += 4
                        continue
                if has_started: block += line[col_num]
                else: new_contents += line[col_num]
                col_num += 1
    return new_contents


if __name__ == "__main__":
    moopath = Path(sys.argv[0]).resolve()
    args = sys.argv[1:]
    globs = Globals(log_enabled=not extract_arg(args, "--silent"))
    stream = extract_arg(args, "--stream")
    if len(args) < 1:
        globs.error("missing arguments for: python moo.py [--silent] [--stream] <source>.moo [args]")
    if globs:
        print("""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣴⣦⡀⠀⠀⠀⠀⠀ ⢀⣤⣶⣄⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⡏⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠹⣿⡇⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣴⣶⣾⣿⣷⣾⣿⣿⣿⣿⣿⣿⣿⣿⣶⣿⣷⣶⣦⡀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⡏  ⣿⣿⡏  ⣿⣿⣿⣿⣿⡇
⠀⠀⠀⣠⣶⣧⠀⠙⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠀
⠀⢀⣼⣿⣿⣿⣷⡦⠀⢸⣿⣿⣿⠿⠿⠿⠿⠿⠿⠿⣿⣿⣿⣷⠀⠀⠀
⢀⣾⣿⣿⣿⣿⣿⡇⠀⠉⠁⣀⣀⣠⣤⣤⣤⣤⣤⣄⣀⣀⠈⠉⠀⠀⠀
⢸⣿⣿⣿⣿⣿⣿⡇⠀⢾⣿⣿⡿⠿⣿⣿⣿⣿⣿⡿⢿⣿⣿⣷⠀⠀⠀
⣿⣿⣿⣿⣿⣿⣿⣿⠀⠸⣿⣿⣧⣀⣹⣿⣿⣿⣿⣀⣰⣿⣿⡟⠀⠀⠀
⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠈⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠋⢀⠀⠀⠀
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣤⣀⣀⡈⠉⠉⠉⠉⣀⣀⣠⣴⠀⠀⠀  
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀
⢸⣿⣿⣿⣿⡏⠉⠉⣿⣿⣿⣿⣿⠿⠿⠿⠿⢿⣿⣿⣿⣿⣿⠀⠀⠀⠀
⠀⢿⣿⣿⣿⠇⠀⠀⠻⣿⣿⣿⠏⠀⠀⠀⠀   ⠿⣿⣿⣿⠇⠀
        """)
    globs.log("MOO", "- version 0.2", color=GREEN)
    path = args[0]
    system_context = Context("<system>")
    system_context["python"] = sys.executable
    system_context["mooargs"] = str(args)
    system_context["cwd"] = str(Path.cwd().resolve())
    system_context["moosafe"] = Region()
    processed = load_file(globs, path, system_context)
    if stream:
        print(processed)
        if globs.schedule: globs.error("there are scheduled tasks but these are disabled in --stream mode")
        sys.exit(0)
    dst = Path(path).with_suffix("")
    if dst.resolve() == moopath:
        globs.error(str(moopath)+" is forbidden from overwriting itself")
    dst.write_text(processed, encoding="utf-8")
    globs.log("monolith", str(dst), color=GREEN)
    schedule = [globs.command(scheduled) for scheduled in globs.schedule]
    for scheduled in schedule: str(scheduled) # sync all
