///**/ schedule g++ moo -o moo -Wall -O3

// Copyright 2026 Emmanouil Krasanakis
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <string>
#include <vector>
#include <memory>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <array>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <regex>
#include <fstream>
#include <sstream>
#include <filesystem>
using namespace std;
using filesystem::path;

const char*  RED   ="\x1b[31m";
const char*  GREEN ="\x1b[32m";
const char*  CYAN  ="\x1b[36m";
const char*  YELLOW="\x1b[33m";
const char*  RESET ="\x1b[0m";
constexpr size_t COMMAND_TYPE = 2;
constexpr size_t PATTERN_TYPE = 3;

class Value {
public:
    virtual const string& str() const = 0;
    virtual const char* type() const {return "str";}
    virtual size_t type_id() const = 0;
    virtual bool match(const string& other) const {return str()==other;}
};

class String: public Value {
public:
    string value;
    explicit String(const string& value):value(value) {}
    const char* type() const override {return "str";}
    const string& str() const override {return value;}
    size_t type_id() const override {return 1;}
};

String* EMPTY_STRING = new String("");
String* TRUE_STRING = new String("True");
String* FALSE_STRING = new String("False");
class Context;
void moo_error(const string& message, const Context* context=nullptr);

static string regex_escape(const string& s) {
    static const auto meta = string{R"(\.^$|()[]{}*+?)"};
    auto out = string{};
    out.reserve(s.size()*2);
    for(char c : s) {
        if(meta.find(c) != string::npos) out.push_back('\\');
        out.push_back(c);
    }
    return out;
}

class Pattern : public Value {
    regex re;
    string raw;
public:
    explicit Pattern(const string& s) : raw(s) {
        string esc;
        for (char c : s) {
            if (c == '*') esc += ".*";
            else esc += regex_escape(string(1, c));
        }
        re = regex("^" + esc + "$");
    }
    const string& str() const override {return raw;}
    const char* type() const override {return "pattern";}
    size_t type_id() const override {return PATTERN_TYPE;}
    bool match(const string& other) const override {return regex_match(other, re);}
};

class Region: public Value {
    string delimiter;
    mutable string cached;
    mutable bool dirty = true;
public:
    vector<Value*> items;
    explicit Region(const string& delim = "\n") : delimiter(delim) {}
    void push(Value* v) { items.push_back(v); dirty = true; }
    const string& str() const override {
        if(!dirty) return cached;
        cached.clear();
        for (auto* v : items) {
            const string& s = v->str();
            if (!cached.empty()) cached += delimiter;
            cached += s;
        }
        dirty = false;
        return cached;
    }
    const char* type() const override { return "region"; }
    size_t type_id() const override { return 4; }
    string descriptive() const {
        ostringstream out;
        for (auto* v : items) out<<"\n     "<<CYAN<< v->type()<<RESET<<" "<<v->str();
        return out.str();
    }
    bool match(const string& value) const override {
        for (auto* v : items) if(v->match(value)) return true;
        return false;
    }
};

class Command : public Value {
    mutable string cached;
    mutable bool executed = false;
public:
    string expression;
    class Context* context;
    explicit Command(const string& expression, class Context* context) : expression(expression), context(context) {}
    size_t type_id() const override {return COMMAND_TYPE;}
    const string& str() const override {
        if(executed) return cached;
#if defined(_WIN32) || defined(_WIN64)
        string full_cmd = "cmd /c \"" + expression + " 2>&1\"";
#else
        string full_cmd = expression + " 2>&1";
#endif
#if defined(_WIN32) || defined(_WIN64)
        FILE* pipe = _popen(full_cmd.c_str(), "r");
#else
        FILE* pipe = popen(full_cmd.c_str(), "r");
#endif
        if (!pipe) {
            string msg = "Cannot open pipe for command: " + expression;
            moo_error(msg, context);
        }
        array<char, 4096> buffer{};
        string stdout_str;
        while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
            stdout_str.append(buffer.data());
        }
#if defined(_WIN32) || defined(_WIN64)
        int rc = _pclose(pipe);
        // _pclose returns the termination status; the low‑order 8 bits are the exit code.
        int exit_code = rc;
#else
        int rc = pclose(pipe);
        int exit_code = WIFEXITED(rc) ? WEXITSTATUS(rc) : rc;
#endif
        if (exit_code != 0) {
            string message =
                string(RED) + "from " + CYAN + "system " + RESET + expression + "\n" +
                string(RED) + "---------------------------------------------" + RESET + "\n" +
                stdout_str +
                string(RED) + "---------------------------------------------" + RESET + "\n" +
                string(RED) + "error" + RESET + " non‑zero exit code " + to_string(exit_code);
            moo_error(message, context);
        }
        cached = move(stdout_str);
        executed = true;
        return cached;
    }
    const string& getExpression() const noexcept { return expression; }
};

class Context {
public:
    size_t row;
    size_t col;
    string path;
    Context* parent;
    bool shared_namespaces;
    bool enabled;
    size_t token_pos;
    string* tokens;
    size_t token_num;
    unordered_map<string, Value*> vars;
    unordered_map<string, Context*> spaces;
    bool wrapper;
    Context(string path, Context* parent, bool shared_namespaces=false): 
        row(0), col(0), 
        path(path), 
        parent(parent), 
        shared_namespaces(shared_namespaces),
        enabled(true),
        token_pos(0),
        tokens(nullptr),
        token_num(0),
        wrapper(false) {}
    inline Context* non_shared_parent() {
        if(!shared_namespaces) return this;
        if(parent) return parent->non_shared_parent();
        return nullptr;
    }
    inline Context* get_existing_namespace(const string& name) const {
        auto it = spaces.find(name);
        if(it!=spaces.end()) return it->second;
        return nullptr;
    }
    inline Context* get_namespace(const string& name) {
        if(name==":") moo_error(":: is not a valid namespace declaration\nIf you did not write this yourself, this error may occur due to unresolved placeholders.", this);
        auto it = spaces.find(name);
        if(it!=spaces.end()) {
            auto ret = it->second;
            ret->tokens = tokens;
            ret->token_num = token_num;
            ret->token_pos = token_pos;
            return ret;
        }
        auto ret = new Context(name, this, true);
        ret->update(row, col);
        ret->tokens = tokens;
        ret->token_num = token_num;
        ret->token_pos = token_pos;
        spaces[name] = ret;
        return ret;
    }
    inline void update(size_t row, size_t col) {this->row=row;this->col=col;}
    inline Value* get_raw_item(const string& name) const {
        auto it = vars.find(name);
        if(it==vars.end()) return nullptr;
        return it->second;
    }
    Value* __unsafe_get(const string& name) const {
        auto it = get_raw_item(name);
        if(it) return it;
        if(parent) return parent->__unsafe_get(name);
        return nullptr;
    }
    Value* get(const string& name) const {
        if(wrapper) return parent->get(name);
        if(name=="moo.log") {
            auto ss = ostringstream{};
            for(const auto& [var, val] : vars) ss<<"/**/ "<<var<<" = "<<val->type()<<" "<<val->str()<<"\n";
            return new String(move(ss.str()));
        }
        auto it = __unsafe_get(name);
        if(!it) moo_error("variable not found: "+name, this);
        return it;
    }
    inline void set(const string& name, Value* value) {
        if(wrapper) return parent->set(name, value);
        if(!value) return;
        if(name=="moo.log") moo_error("cannot overwrite moo.log", this);
        if(name=="moo.safe") moo_error("cannot shadow moo.log", this);
        auto it = get_raw_item(name);
        if(it) {
            if(it->type_id()!=value->type_id()) moo_error("mismatching previous type for variable: "+name, this);
            if(value->type_id()!=COMMAND_TYPE) {if(value->str()!=it->str()) moo_error("mismatching previous value for variable: "+name, this);}
            else if(((Command*)it)->expression!=((Command*)value)->expression) moo_error("mismatching previous value for variable: "+name, this);
        }
        vars[name] = value;
    }
    inline void remove(const string& name) {
        vars.erase(name);
    }
};

void moo_error(const string& message, const Context* context) {
    cout<<RED<<"error"<<RESET<<" "<<message<<"\n";
    while(context) {
        if(!context->parent || context->shared_namespaces) cout<<RED<<"   in namespace "<<YELLOW<<context->path<<RESET<<"\n";
        else cout<<RED<<"   in "<<YELLOW<<context->path<<RESET<<" line "<<(context->row+1)<<" column "<<(context->col+1)<<"\n";
        if(context->tokens) {
            auto toks = context->tokens;
            auto i = context->token_pos;
            if(i>=0 && i<context->token_num) {
                auto start = i;
                auto first_tok = string{""};
                auto end_tok = string{""};
                while(start>0) {
                    auto pos = toks[start-1].rfind('\n');
                    if(pos!=string::npos) {
                        first_tok  = toks[start-1].substr(pos + 1);
                        break;   
                    }
                    start -= 1;
                }
                auto end = i;
                while(end<context->token_num) {
                    auto pos = toks[end].find('\n');
                    if(pos!=string::npos) {
                        end_tok = toks[end].substr(0, pos);
                        break;
                    }
                    end += 1;
                }
                auto snippet = RED+string{"   └─"}+RESET;
                auto carret = string("     ");
                snippet += first_tok;
                snippet += string(' ', first_tok.size());
                for(size_t k=start;k<end;++k) {
                    snippet += toks[k];
                    if(k<i) carret += string(toks[k].size(), ' ');
                }
                carret += RED+string(toks[i].size(), '^')+RESET;
                snippet += end_tok;
                cout<<snippet<<"\n";
                cout<<carret<<"\n";
            }
        }
        context = context->parent;
    }
    exit(1);
}

class Globals {
    unordered_map<string, Command*> commands;
    size_t temp_counter;
    bool log_enabled;
public:
    vector<string> schedule;
    Globals(bool log_enabled): temp_counter(0), log_enabled(log_enabled) {}
    inline Command* command(const string& expression, Context* context) {
        log("  system", expression);
        auto it = commands.find(expression);
        if(it!=commands.end()) return it->second;
        auto command = new Command(expression, context);
        commands[expression] = command;
        return command;
    }
    inline void log(string kind, string message, const char* color=nullptr) {
        if(!color) color = CYAN;
        if(log_enabled) cout<<color<<kind<<RESET<<" "<<message<<"\n";
    }
    string create_temp() {return "temp"+to_string(temp_counter++);}
};

bool extract_arg(vector<string>& args, const string& name) {
    auto it = find(args.begin(), args.end(), name);
    if(it != args.end()) {
        args.erase(it);
        return true;
    }
    return false;
}

static const regex token_regex(R"((\s+|:|\\+|/\*\*/|/|=|\$|[{}]))");
Value* parse_block(Globals&, string*, Context*, size_t, size_t);
string consume_block(Globals&, string*, Context*, size_t, size_t);
string load_file(Globals&, const string&, Context* =nullptr);

string consume_block(Globals& globs, string* toks, Context* ctx, size_t pos, size_t num) {
    auto result = string{""};
    while(pos<num) {
        const string& tk = toks[pos];
        if (tk == "{") {
            size_t start = pos;
            size_t depth = 0;
            while(pos < num) {
                if(toks[pos] == "{") ++depth;
                else if(toks[pos] == "}") {
                    --depth;
                    if(depth == 0) break;
                }
                ++pos;
            }
            result += parse_block(globs, toks, ctx, start+1, pos)->str();
            ++pos; // skip closing '}'
        } 
        else {
            result += tk;
            ++pos;
        }
    }
    return result;
}

Value* parse_block(Globals& globs, string* raw, Context* ctx, size_t pos, size_t num) {
    while(num>pos && raw[num-1].find_first_not_of(" \t\r\n") == string::npos) --num;
    if(pos >= num) moo_error("empty block", ctx);
    auto skip_space = [&](size_t& p) {while (p < num && raw[p].find_first_not_of(" \t\r\n") == string::npos) ++p;};
    auto find_next_colon = [&](size_t p) {
        int dep = 0;
        size_t colon = p;
        while (colon < num) {
            if (raw[colon] == "{") ++dep;
            if (raw[colon] == "}") --dep;
            if (dep == 0 && raw[colon] == ":") break;
            ++colon;
        }
        return colon;
    };
    skip_space(pos);
    if(pos == num - 1) {
        ctx->token_pos = pos;
        return ctx->get(raw[pos]);
    }

    while(pos < num) {
        skip_space(pos);
        if (pos >= num) break;
        ctx->token_pos = pos;
        const string& tok = raw[pos];
        pos += 1;
        skip_space(pos);
        if (tok == "enabled") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            if (blk == "True") ctx->enabled = true;
            else if (blk == "False") ctx->enabled = false;
            else moo_error("enabled expects True/False", ctx);
            return EMPTY_STRING;
        }
        else if (tok == "path") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            return new String(path(blk).lexically_normal().string());
        }
        else if (tok == "system") {
            auto prev_pos = ctx->token_pos;
            auto cmd = consume_block(globs, raw, ctx, pos, num);
            ctx->token_pos = prev_pos;
            auto safe = dynamic_cast<Region*>(ctx->get("moo.safe"));
            if(cmd.find("..") != string::npos) moo_error("‘..’ not allowed in system command", ctx);
            if(!safe->match(cmd))
                moo_error("command not permitted by 'moo.safe': "+cmd+"\n  Current permissions:"+safe->descriptive(), ctx);
            return globs.command(cmd, ctx);
        }
        else if (tok == "import") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            return new String{load_file(globs, blk, ctx)};
        }
        else if (tok == "read") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            globs.log("    read", blk);
            ifstream f(blk);
            if(!f.is_open()) moo_error("failed to open file: "+blk, ctx);
            ostringstream ss;
            ss << f.rdbuf();
            return new String(ss.str());
        }
        else if (tok == "str" || tok == "$") return new String(consume_block(globs, raw, ctx, pos, num));
        else if (tok == "pattern") return new Pattern(consume_block(globs, raw, ctx, pos, num));
        else if (tok == "print") {
            cout<<consume_block(globs, raw, ctx, pos, num)<<"\n";
            return EMPTY_STRING;
        }
        else if (tok == "if") {
            auto colon = find_next_colon(pos);
            auto cond = parse_block(globs, raw, ctx, pos, colon)->str();
            if(cond == "True") return parse_block(globs, raw, ctx, colon+1, num);
            else if(cond!="False") moo_error("conditions can only be True/False", ctx);
            return EMPTY_STRING;
        }
        else if(tok == "for") {
            string varname = raw[pos];
            pos += 1;
            skip_space(pos);
            if(raw[pos]!="=") moo_error("expecting '=' after loop bariable", ctx);
            pos += 1;
            skip_space(pos);
            auto colon = find_next_colon(pos);
            auto iter_blk = parse_block(globs, raw, ctx, pos, colon);
            pos = colon+1;
            auto iter_val = iter_blk;
            auto src = dynamic_cast<Region*>(iter_val);
            if(!src) {
                src = new Region();
                src->push(iter_val);
            }
            auto out = new Region();
            for (auto* item : src->items) {
                ctx->set(varname, item);
                auto body = parse_block(globs, raw, ctx, pos, num);
                out->push(body);
                ctx->remove(varname);
            }
            return out;
        }
        else if(tok == "match") {
            auto colon = find_next_colon(pos);
            auto iter_blk = parse_block(globs, raw, ctx, pos, colon);
            pos = colon+1;
            auto iter_val = iter_blk;
            skip_space(pos);
            auto value = consume_block(globs, raw, ctx, pos, num);
            if(iter_val->match(value)) return TRUE_STRING;
            return FALSE_STRING;
        }
        else if (tok == "list") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            auto r = new Region();
            r->push(new String(blk));
            return r;
        }
        else if (tok == "range") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            istringstream ss(blk);
            long long a, b;
            ss >> a >> b;
            auto r = new Region();
            for(long long i = a; i < b; ++i) r->push(new String(to_string(i)));
            return r;
        }
        else if (tok == "placeholder") {
            auto blk = consume_block(globs, raw, ctx, pos, num);
            auto src = ctx->get(blk);
            auto list = dynamic_cast<Region*>(src);
            if(!list) moo_error("placeholder needs a region", ctx);
            auto temp = "/***::" + globs.create_temp() + "::***/";
            ctx->set(temp, list);
            return new String(temp);
        }
        else if (tok == "do") {
            ctx->token_pos = pos;
            auto expanded = consume_block(globs, raw, ctx, pos, num);
            auto new_toks = vector<string>{};
            auto m = smatch{};
            auto searchStart = string::const_iterator{expanded.cbegin()};
            while(regex_search(searchStart, expanded.cend(), m, token_regex)) {
                if (m.prefix().length()) new_toks.push_back(m.prefix());
                new_toks.push_back(m[0]);
                searchStart = m.suffix().first;
            }
            if(searchStart!=expanded.cend()) new_toks.push_back(string(searchStart, expanded.cend()));
            auto new_tok_array = new string[new_toks.size()];
            for(size_t i=0;i<new_toks.size();++i) new_tok_array[i] = new_toks[i];
            auto backup_ctx = new Context(ctx->path, ctx);
            backup_ctx->tokens = new_tok_array;
            backup_ctx->token_num = new_toks.size();
            backup_ctx->token_pos = 0;
            backup_ctx->wrapper = true;
            auto sub = parse_block(globs, new_tok_array, backup_ctx, 0, new_toks.size());
            return sub;
        }
        else if (raw[pos] == "=") {
            pos += 1;
            auto val = parse_block(globs, raw, ctx, pos, num);
            ctx->set(tok, val);
            return EMPTY_STRING;
        }
        else if (raw[pos] == ":") {
            Context* ns = ctx->get_namespace(tok);
            if(!ns->enabled) return EMPTY_STRING;
            pos += 1;
            skip_space(pos);
            return parse_block(globs, raw, ns, pos, num);
        }
        else if (raw[pos] == "+") {
            // “+=” – only valid after a variable name and “=”
            ctx->token_pos = pos;
            if (raw[pos + 1] != "=") moo_error("expected '+='", ctx);
            pos += 2;
            skip_space(pos);
            ctx->token_pos = pos;
            auto var = ctx->get(tok);
            auto val = parse_block(globs, raw, ctx, pos, num);
            if(auto* r = dynamic_cast<Region*>(var))
                r->push(val);
            else moo_error("'+=' only works on lists", ctx);
            return EMPTY_STRING;
        }
        else if (tok == "schedule") {
            auto val = consume_block(globs, raw, ctx, pos, num);
            globs.schedule.push_back(val);
            return EMPTY_STRING;
        }
        else if (tok == "/**/") {
            --pos;
            ctx->token_pos = pos;
            auto reg = new Region();
            while(pos < num) {
                pos++;
                size_t depth = 0;
                while(pos < num) {
                    if(raw[pos] == "{") ++depth;
                    if(raw[pos] == "}") --depth;
                    if(raw[pos] == "/**/" && !depth) break;
                    ++pos;
                }
                reg->push(parse_block(globs, raw, ctx, ctx->token_pos+1, pos));
                ctx->token_pos = pos;
            }
            if(reg->items.size()<=1) moo_error("'/**/' is allowed here only to designate the start of a list whose elements are separated by that symbol", ctx);
            return reg;
        }
        else if (tok == "{") moo_error("unexpected '{", ctx);
        else moo_error("unexpected command: "+tok, ctx);
    }
    if(pos<num) moo_error("broken syntax", ctx);
    return EMPTY_STRING;
}

string load_file(Globals& globs, const string& filename, Context* parent) {
    Context* ctx = new Context(filename, parent);
    globs.log("  import", filename);
    ifstream in(filename);
    if (!in) moo_error("cannot open file: " + filename);
    ostringstream out;
    string line;
    size_t in_block = 0;
    string block;
    size_t row = -1;
    while(getline(in, line)) {
        row += 1;
        size_t line_size = line.size();
        bool show_line_end = true;
        for (size_t i = 0; i < line_size;) {
            if (i<=line_size-4 && !in_block && line.compare(i, 4, "/**/")==0) {
                i += 4;
                ctx->update(row, i);
                block = line.substr(i);
                auto tokens = vector<string>{};
                auto m = smatch{};
                auto it = string::const_iterator{block.cbegin()};
                while (regex_search(it, block.cend(), m, token_regex)) {
                    if(m.prefix().length()) tokens.push_back(m.prefix());
                    tokens.push_back(m[0]);
                    it = m.suffix().first;
                }
                if (it!=block.cend()) tokens.push_back(string(it, block.cend()));
                auto raw_toks = new string[tokens.size()];
                for(size_t i=0;i<tokens.size();++i) raw_toks[i] = tokens[i];
                ctx->tokens = raw_toks;
                ctx->token_num = tokens.size();
                auto val = parse_block(globs, raw_toks, ctx, 0, tokens.size());
                out << val->str();
                block.clear();
                show_line_end = false;
                break;
            }
            if (i<=line_size-4 && !in_block && line.compare(i, 4, "/***")==0) {
                in_block = 1;
                i += 4;
                ctx->update(row, i);
                continue;
            }
            if (i<=line_size-4 && in_block==1 && line.compare(i, 4, "***/")==0) {
                i += 4;
                auto tokens = vector<string>{};
                auto m = smatch{};
                auto it= string::const_iterator{block.cbegin()};
                while(regex_search(it, block.cend(), m, token_regex)) {
                    if(m.prefix().length()) tokens.push_back(m.prefix());
                    tokens.push_back(m[0]);
                    it = m.suffix().first;
                }
                if(it!=block.cend()) tokens.push_back(string(it, block.cend()));
                auto raw_toks = new string[tokens.size()];
                for(size_t i=0;i<tokens.size();++i) raw_toks[i] = tokens[i];
                ctx->tokens = raw_toks;
                ctx->token_num = tokens.size();
                auto val = parse_block(globs, raw_toks, ctx, 0, tokens.size());
                out << val->str();
                block.clear();
                in_block = 0;
                continue;
            }
            if(in_block) {
                if (i<line_size-4 && line.compare(i, 4, "/***")==0) {
                    ctx->tokens = &block;
                    ctx->token_num = 1;
                    ctx->token_pos = 0;
                    moo_error("moo code block never closed", ctx);
                }
                if (i<line_size-4 && in_block>1 && line.compare(i, 4, "***/")==0) in_block--;
                block += line[i];
                ++i;
                continue;
            } 
            out<<line[i];
            ++i;
        }
        if(show_line_end) out << '\n';
    }
    for (auto& [k, v] : ctx->vars) {
        if (k.rfind("/***::", 0) == 0) {
            auto placeholder = k;
            auto repl = v->str();
            auto content = out.str();
            size_t pos = 0;
            while ((pos = content.find(placeholder, pos)) != string::npos) {
                content.replace(pos, placeholder.size(), repl);
                pos += repl.size();
            }
            out.str("");
            out.clear();
            out << content;
        }
    }
    return out.str();
}

int main(int argc, char* argv[]) {
    vector<string> args(argv + 1, argv + argc);
    bool nocolor = extract_arg(args, "--nocolor");
    bool silent  = extract_arg(args, "--silent");
    bool stream  = extract_arg(args, "--stream");
    if(nocolor) RED = GREEN = CYAN = YELLOW = RESET = "";
    if(args.empty()) {
        cerr << "usage: moo.cpp [--silent] [--stream] <script>.moo [script‑args...]\n";
        return 1;
    }

    Globals globs(!silent);
    globs.log("MOO", "- version 0.5", GREEN);
    const string script_path = args[0];

    auto system_ctx = new Context("MOO", nullptr);
    system_ctx->vars["moo.run"] = new String(string(argv[0]));
    system_ctx->vars["moo.safe"] = new Region();
    auto args_reg = new Region();
    for(size_t i = 1; i < args.size(); ++i) args_reg->push(new String(args[i]));
    system_ctx->vars["moo.args"] = args_reg;
    system_ctx->vars["moo.cwd"] = new String(filesystem::current_path().string());
    system_ctx->vars["moo.symbols.line"] = new String("\n");
    system_ctx->vars["moo.symbols.space"] = new String(" ");
    system_ctx->vars["moo.symbols.comma"] = new String(",");
    system_ctx->vars["moo.python"] = new String("python3");

    auto processed = load_file(globs, script_path, system_ctx);
    if (stream) {
        cout << processed;
        if(!globs.schedule.empty()) moo_error("scheduled tasks are disabled in --stream mode");
        return 0;
    }
    auto dst = path(script_path).replace_extension("");
    if(dst == path(argv[0]).lexically_normal()) moo_error(dst.string() + " is forbidden from overwriting itself");
    auto out = ofstream{dst};
    out<<processed;
    out.close();
    globs.log("monolith", dst.string(), GREEN);
    if(!globs.schedule.empty()) {
        globs.log("schedule", "", GREEN);
        vector<Command*> scheduled;
        for(const auto& s : globs.schedule) scheduled.push_back(globs.command(s, system_ctx));
        for(auto* c : scheduled) c->str();  // force execution and sync
    }
    return 0;
}