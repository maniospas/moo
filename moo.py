import sys, base64, subprocess, tempfile, atexit, re
from pathlib import Path
from typing import Any, Callable
RED, GREEN, CYAN, RESET = "\x1b[31m", "\x1b[32m", "\x1b[36m", "\x1b[0m"

class Region:
    def __init__(self, sep="\n"):
        self.contents = ""
        self.sep = sep
    
    def push(self, contents):
        if self.contents: self.contents += self.sep
        self.contents += contents
    
    def __str__(self):
        return self.contents

class Command:
    def __init__(self, expression):
        self.expression = expression
        self.cached = None
        self.proc = subprocess.Popen(expression, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
    def __str__(self):
        if self.cached is not None: return self.cached
        stdout, stderr = self.proc.communicate()
        assert self.proc.returncode==0, f"non-zero exit code {self.proc.returncode}\n{stderr}"
        self.cached = str(stdout)
        return self.cached


class Context:
    def __init__(self, path="<inline>", parent=None):
        self.path = path
        self.parent = parent
        self.row = 0
        self.col = 0
        self.vars = dict()

    def update(self, row, col):
        self.row = row
        self.col = col

    def __setitem__(self, name, value):
        existing = self.vars.get(name, None)
        if existing: 
            assert isinstance(existing, Region), "Can append but not reassign to region: "+name
            assert isinstance(value, Command)==isinstance(existing, Command), "Conflicting variable type (command vs const): "+name
            if not isinstance(value, Command): assert value == existing, "Cannot overwrite previously different variable: "+name
            else: assert value.expression == existing.expression, "Cannot overwrite previously different variable: "+name
            return
        self.vars[name] = value
    
    def get_raw_item(self, name):
        existing = self.vars.get(name, None)
        if existing is None and self.parent: return self.parent.get_raw_item(name)
        return existing

    def __getitem__(self, name):
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

    def command(self, expression):
        existing = self.commands.get(expression, None)
        if existing: return existing
        existing = Command(expression)
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
            print(RED, " at", CYAN+context.path+RESET, "line", context.row+1, "column", context.col+1, file=sys.stderr)
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
            raw_parts = re.split(r'(\s+|=|[{}])', block)
            tokens = [p for p in raw_parts if p != ""]
        if num_tokens is None: num_tokens = len(tokens)
        assert pos<num_tokens, "empty block"
        if pos==num_tokens-1:
            return context[tokens[pos]], num_tokens+1
        returned = ""
        while pos<num_tokens:
            token = tokens[pos]
            if token.isspace(): 
                pos += 1
                continue
            while pos<num_tokens-1 and tokens[pos+1].isspace(): 
                pos += 1
            if pos<num_tokens-2 and tokens[pos+1]=="=":
                returned, pos = parse_block(globs, block, context, pos+2, num_tokens)
                context[token] = returned
                returned = ""
                assert pos>=num_tokens-1, "leftover code after assignment"
            elif token=="command":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = globs.command(returned)
            elif token=="import":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = load_file(globs, returned, context)
            elif token=="const":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
            elif token=="pass":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                returned = ""
            elif token=="append":
                pos += 1
                varname = tokens[pos]
                var = context.get_raw_item(varname)
                assert var is not None, "cannot find variable: "+varname
                assert isinstance(var, Region), "can only append to regions: "+varname
                while pos<num_tokens-1 and tokens[pos+1].isspace(): 
                    pos += 1
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens)
                var.push(returned)
                returned = ""
            elif token=="region":
                pos += 1
                returned = Region()
                assert pos>=num_tokens-1, "leftover code after declaring region"
            elif token=="do":
                returned, pos = consume_block(globs, tokens, context, pos+1, num_tokens, variable_expansion_only=True)
                new_raw_parts = re.split(r'(\s+|=|[{}])', returned.replace("\n", " ").strip())
                new_tokens = [p for p in new_raw_parts if p != ""]+tokens[pos+1:num_tokens]
                returned, _ = parse_block(globs, new_tokens, context)
            elif token=="{": raise Exception("cannot start a {} block here\nExpecting a function or variable name. Perhaps you meant to preface it with `do`?")
            else: raise Exception("unknown function: "+token+"\nPerhaps you meant to preface it with `const`?")
            pos += 1
        return returned, pos
    except Exception as e:
        globs.error(str(e), context)
    except AssertionError as e:
        globs.error(str(e), context)


def load_file(globs: Globals, path: str, parent_context: Context=None):
    context = Context(path, parent=parent_context)
    if not path.endswith(".moo"):
        globs.error("for safety, only .moo files can be parsed: "+path, context)
    # found = globs.imported.get(path, None)
    # if found is not None: return found
    globs.log("import", path)
    has_started = 0
    block = ""
    new_contents = ""
    with open(path) as file:
        for line_num, line in enumerate(file):
            line_length = len(line)
            col_num = 0
            while col_num<line_length:
                if col_num<=line_length-4 and line[col_num:col_num+4]=="***/":
                    has_started -= 1
                    if not has_started:
                        col_num += 4
                        returned = parse_block(globs, block, context)
                        new_contents += str(returned[0])
                        block = ""
                        continue
                if col_num<=line_length-4 and line[col_num:col_num+4]=="/***":
                    has_started += 1
                    if has_started==1:
                        context.update(line_num, col_num)
                        col_num += 4
                        continue
                if has_started: block += line[col_num]
                else: new_contents += line[col_num]
                col_num += 1
    #globs.imported[path] = new_contents
    return new_contents



if __name__ == "__main__":
    args = sys.argv[1:]
    globs = Globals(log_enabled=not extract_arg(args, "--silent"))
    stream = extract_arg(args, "--stream")
    if len(args) != 1:
        globs.error("missing arguments for: python moo.py [--silent] [--stream] <source>.in")
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
    path = args[0]
    system_context = Context("<system>")
    system_context["python"] = sys.executable
    system_context["cwd"] = str(Path.cwd().resolve())
    processed = load_file(globs, path, system_context)
    if stream:
        print(processed)
        sys.exit(0)
    dst = Path(path).with_suffix("")
    dst.write_text(processed, encoding="utf-8")
    globs.log("monolith", str(dst), color=GREEN)
