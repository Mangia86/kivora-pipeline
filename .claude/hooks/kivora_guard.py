#!/usr/bin/env python3
"""kivora_guard: hook PreToolUse del proyecto Kivora (solo biblioteca estandar).

Claude Code lo ejecuta antes de cada llamada a Bash, PowerShell, Edit, Write o NotebookEdit y le pasa la
llamada como JSON por stdin. Salida 2 = BLOQUEA (el motivo va por stderr y llega al agente); salida 0 con
JSON `permissionDecision: ask` = pide confirmacion a la persona; salida 0 sin mas = deja seguir.
Falla CERRADO: cualquier error interno bloquea (el hook se registra con "onFailure": "block").

Reglas
  R1  No escribir en data/inbox/** ni deliveries/**.
  R2  No reescribir el historial: amend, rebase, reset --hard, push --force/--delete, push a un remoto que
      no sea origin, borrar o mover tags.
  R3  Puerta del commit: trailer Co-Authored-By, sin `-a`, `git add` y `git commit` en llamadas separadas,
      indice sin .jsonl/.env/output/*.db, entregas intactas y en commit propio, sin espacios sobrantes.
  R4  Orden de fases: el codigo (kivora/, sql/, tests/, tasks.py) solo se toca si la fase en curso y los
      artefactos ya commiteados (spec, plan revisado, impacto) lo permiten.
  R5  `tasks.py deliver N` solo en su fase: la 1 tras phase-1; la 2 tras phase-4 y con la entrega 1 recibida.
  R6  Un settings.json invalido desactiva TODAS las protecciones: se bloquea escribirlo invalido; las
      escrituras por shell en .claude/** o CLAUDE.md piden confirmacion.

Recuperacion manual (solo una persona): poner {"disableAllHooks": true} en .claude/settings.local.json (no se
versiona), corregir el fallo, validar con `claude doctor` y quitar esa linea.
Probar sin Claude:  uv run python -m pytest .claude/hooks -q
"""
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
ROOT = str(PROJECT).replace("\\", "/").rstrip("/")
TRAILER = re.compile(r"co-authored-by:\s*claude code\s*<noreply@anthropic\.com>", re.I)
RECOVERY = ('Recuperacion manual (solo una persona): {"disableAllHooks": true} en .claude/settings.local.json, '
            "corregir, validar con `claude doctor` y quitar la linea.")

HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\1\b", re.S)
HERESTR = re.compile(r"@(['\"])[ \t]*\n(.*?)\n\1@", re.S)
REDIR = re.compile(r"(?<![0-9&=<-])>{1,2}\s*([^\s&|;]+)")
PY_WRITE = re.compile(
    r"open\([^)]*['\"][wax+]b?\+?['\"]|\.write_text\(|\.write_bytes\(|shutil\.(?:copy|copy2|copyfile|copytree|move|rmtree)|"
    r"os\.(?:remove|unlink|rename|replace|rmdir|makedirs|mkdir)|\.unlink\(|\.rename\(|\.touch\(|\.mkdir\(|\.rmdir\(")
WRITE_ANY = {"rm", "rmdir", "rd", "ri", "del", "erase", "mv", "move", "mi", "ren", "rename", "rni", "mkdir", "md", "ni",
             "touch", "truncate", "tee", "dd", "ln", "install", "chmod", "chown", "attrib", "icacls", "set-content", "sc",
             "add-content", "ac", "out-file", "clear-content", "clc", "remove-item", "move-item", "rename-item",
             "new-item", "set-itemproperty", "tee-object"}
COPY_LIKE = {"cp", "copy", "cpi", "copy-item", "xcopy", "robocopy"}
GIT_PATH_WRITE = {"checkout", "restore", "clean", "stash", "rm", "mv", "apply", "am", "update-index"}
HOOK_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "Notification", "UserPromptSubmit",
               "UserPromptExpansion", "SessionStart", "SessionEnd", "Stop", "StopFailure", "SubagentStart", "SubagentStop",
               "PreCompact", "PostCompact", "PreModelSwitch", "PostModelSwitch", "PermissionRequest", "PermissionDenied",
               "Setup", "TeammateIdle", "TaskCreated", "TaskCompleted", "Elicitation", "ElicitationResult", "ConfigChange",
               "WorktreeCreate", "WorktreeRemove", "InstructionsLoaded", "CwdChanged", "FileChanged", "DirectoryAdded",
               "MessageDisplay"}


class Deny(Exception):
    def __init__(self, rule, msg):
        super().__init__(f"BLOQUEADO [{rule}]: {msg}")


class Ask(Exception):
    def __init__(self, rule, msg):
        super().__init__(f"[{rule}] {msg}")


# ------------------------------------------------------------------ utilidades de git y rutas
def git(*args):
    return subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def tags():
    return set(git("tag", "--list").stdout.split())


def in_head(path):
    return git("cat-file", "-e", f"HEAD:{path}").returncode == 0


def rel_path(arg, cur):
    """Ruta relativa al proyecto, en minusculas y con '/', o None si cae fuera o no se puede resolver."""
    a = arg.strip("'\"").replace("\\", "/")
    if a.startswith("~"):
        return None
    m = re.match(r"^/([a-zA-Z])/(.*)$", a)  # estilo Git Bash: /c/Users/...
    if m:
        a = f"{m.group(1)}:/{m.group(2)}"
    if a.lower() == ROOT.lower() or a.lower().startswith(ROOT.lower() + "/"):
        a, base = a[len(ROOT):].lstrip("/"), ""
    elif re.match(r"^[a-zA-Z]:/", a) or a.startswith("/"):
        return None
    elif cur is None:
        return None
    else:
        base = cur
    p = posixpath.normpath(posixpath.join(base, a)) if a else base
    p = "" if p == "." else p
    return None if p.startswith("..") else p.lower()


def category(rel):
    if rel is None:
        return None
    if rel in ("data/inbox", "deliveries") or rel.startswith(("data/inbox/", "deliveries/")):
        return "inbox"
    if rel == "tasks.py" or rel.startswith(("kivora/", "sql/", "tests/")):
        return "code"
    if rel == "claude.md" or rel.startswith(".claude/"):
        return "claude"
    return None


# ------------------------------------------------------------------ analisis de comandos de shell
def extract_code(cmd):
    bodies = []

    def grab(m):
        bodies.append(m.group(2))
        return " "

    return HERESTR.sub(grab, HEREDOC.sub(grab, cmd)), bodies


def split_statements(text):
    out, cur, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch in ";\n|" or text[i:i + 2] == "&&":
            if text[i:i + 2] in ("&&", "||"):
                i += 1
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def tokenize(stmt):
    try:
        toks = shlex.split(stmt, posix=True)
    except ValueError:
        toks = [t.strip("'\"") for t in re.findall(r"""[^\s'"]+|'[^']*'|"[^"]*\"""", stmt)]
    toks = [t.lower() for t in toks]
    while toks and toks[0] in ("uv", "env", "time", "sudo", "command", "exec", "call", "&", "."):
        word, toks = toks[0], toks[1:]
        if word == "uv":
            toks = toks[1:] if toks and toks[0] == "run" else toks
            while toks and toks[0].startswith("-"):
                toks = toks[1:]
    return toks


def parse_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-c", "--git-dir", "--work-tree") else 1  # los tokens van en minusculas: cubre -C y -c
    return (args[i] if i < len(args) else ""), args[i + 1:]


def analyze(command, cwd):
    text, bodies = extract_code(command.replace("\\", "/"))
    cur, res = cwd, {"writes": [], "git": [], "deliver": [], "pycode": list(bodies)}
    for stmt in split_statements(text):
        for m in REDIR.finditer(stmt):
            target = m.group(1).strip("'\"")
            if target.lower() not in ("$null", "/dev/null", "nul"):
                res["writes"].append(rel_path(target, cur))
        toks = tokenize(stmt)
        if not toks:
            continue
        word, args = toks[0], toks[1:]
        pos = [a for a in args if not a.startswith("-")]
        for i, t in enumerate(toks):
            if t.endswith("tasks.py") and toks[i + 1:i + 2] == ["deliver"] and toks[i + 2:i + 3] and toks[i + 2].isdigit():
                res["deliver"].append(int(toks[i + 2]))
        if word in ("cd", "chdir", "set-location", "sl", "pushd") and pos:
            cur = rel_path(pos[0], cur)
        elif word in WRITE_ANY:
            res["writes"] += [rel_path(a, cur) for a in pos]
        elif word in COPY_LIKE:
            p = [a for a in pos if not (a.startswith("/") and len(a) <= 3)]
            if p:
                res["writes"].append(rel_path(p[-1], cur))
        elif word in ("sed", "perl") and any(re.fullmatch(r"-[a-z]*i[a-z]*", a) or a == "--in-place" for a in args):
            res["writes"] += [rel_path(a, cur) for a in pos[1:]]
        elif word == "git":
            sub, rest = parse_git(args)
            res["git"].append((sub, rest))
            if sub in GIT_PATH_WRITE:
                res["writes"] += [rel_path(a, cur) for a in rest if not a.startswith("-")]
        elif word in ("python", "python3", "py", "node", "pwsh", "powershell"):
            res["pycode"] += [args[i + 1] for i, a in enumerate(args) if a in ("-c", "-command", "-e") and i + 1 < len(args)]
    return res


# ------------------------------------------------------------------ reglas
def code_gate():
    """R4: el codigo del pipeline solo se toca cuando la fase y los artefactos ya commiteados lo permiten."""
    nums = [int(m.group(1)) for t in tags() if (m := re.fullmatch(r"phase-(\d+)", t))]
    fase = max(nums, default=0) + 1
    if fase <= 2:
        raise Deny("R4", f"fase {fase} en curso: el enunciado exige cerrarla sin cambios en kivora/, sql/ ni tests/.")
    if fase == 3:
        raise Ask("R4", "Fase 3 (configuracion del agente): el codigo del pipeline no forma parte de esta fase. ¿Confirmas?")
    spec, plan = "docs/specs/KIV-101/spec.md", "docs/specs/KIV-101/plan.md"
    missing = [p for p in (spec, plan) if not in_head(p)]
    if not missing:
        if not re.search(r"Revisi[oó]n del plan", git("show", f"HEAD:{plan}").stdout):
            missing.append("seccion 'Revision del plan' en plan.md")
        if int(git("rev-list", "--count", "HEAD", "--", plan).stdout.strip() or 0) < 2:
            missing.append("al menos 2 commits sobre plan.md (borrador y revision)")
    if missing:
        raise Deny("R4", "antes del codigo falta commitear: " + "; ".join(missing) + ".")
    if fase >= 5:
        if not in_head("docs/specs/KIV-102/impact.md"):
            raise Deny("R4", "impacto antes del codigo: falta commitear docs/specs/KIV-102/impact.md.")
        if not (in_head("docs/specs/KIV-102/spec.md") and in_head("docs/specs/KIV-102/plan.md")):
            raise Ask("R4", "Faltan spec.md o plan.md de KIV-102 commiteados. ¿Seguro que quieres tocar codigo ya?")


def deliver_gate(n):
    """R5: cada entrega en su fase."""
    t = tags()
    if n == 1 and "phase-1" not in t:
        raise Deny("R5", "deliver 1 pertenece a la fase 2: cierra antes la fase 1 (tag phase-1).")
    if n == 2:
        if "phase-4" not in t:
            raise Deny("R5", "deliver 2 es el primer paso de la fase 5: exige cerrar la fase 4 (tag phase-4).")
        if not ((PROJECT / "docs/tickets/KIV-101.md").exists() and (PROJECT / "data/inbox/2026-09-07").exists()):
            raise Deny("R5", "antes de la entrega 2 hay que haber recibido la 1.")


def commit_gate(command, rest, compound_add):
    """R3: puerta del commit."""
    if compound_add:
        raise Deny("R3", "separa `git add` y `git commit` en llamadas distintas (el guard revisa el indice ya preparado).")
    if any(t == "--all" or re.fullmatch(r"-[a-z]*a[a-z]*", t) for t in rest):
        raise Deny("R3", "no uses `commit -a`: añade con `git add` los ficheros concretos.")
    if not any(t in ("-m", "--message") or t.startswith(("-m", "--message=")) for t in rest):
        raise Deny("R3", "usa `git commit -m` con el mensaje en la propia orden (así se puede comprobar el trailer).")
    if not TRAILER.search(command):
        raise Deny("R3", "falta `Co-Authored-By: Claude Code <noreply@anthropic.com>` en el mensaje (regla de CLAUDE.md).")
    raw = git("diff", "--cached", "--name-status", "--no-renames", "-z").stdout.split("\0")
    staged = [(raw[i], raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
    for st, p in staged:
        lp = p.lower()
        if lp.endswith((".jsonl", ".db")) or re.search(r"(^|/)\.env(\.|$)", lp) or lp.startswith("output/"):
            raise Deny("R3", f"no se commitea `{p}` (transcripciones, secretos o salidas regenerables).")
        if category(lp) == "inbox" and st != "A":
            raise Deny("R3", f"`{p}` es una entrega: solo se puede AÑADIR con `tasks.py deliver N`, no modificar ni borrar.")
    added = [p for st, p in staged if st == "A" and p.lower().startswith("data/inbox/")]
    if added:
        others = [p for _, p in staged if not p.lower().startswith("data/inbox/") and not re.fullmatch(r"docs/tickets/kiv-10\d\.md", p.lower())]
        if others:
            raise Deny("R3", "la entrega va en un commit propio: quita " + ", ".join(others[:3]) + ".")
        blobs = {}
        for line in git("ls-files", "-s", "--", "data/inbox", "deliveries").stdout.splitlines():
            meta, _, path = line.partition("\t")
            blobs[path.lower()] = meta.split()[1]
        for p in added:
            tail = p.lower()[len("data/inbox/"):]
            if blobs.get(p.lower()) not in {blobs.get(f"deliveries/delivery-{n}/{tail}") for n in (1, 2)} - {None}:
                raise Deny("R3", f"`{p}` no coincide byte a byte con ninguna entrega de deliveries/.")
    chk = git("diff", "--cached", "--check", "--", ".", ":(exclude)docs/sessions")
    if chk.returncode != 0 and chk.stdout.strip():
        raise Deny("R3", "`git diff --cached --check` falla: " + chk.stdout.strip().splitlines()[0])


def check_settings(text):
    """R6: devuelve el primer problema que dejaria el settings.json invalido (o None)."""
    try:
        cfg = json.loads(text)
    except ValueError as exc:
        return f"JSON invalido ({exc})"
    if not isinstance(cfg, dict):
        return "la raiz debe ser un objeto"
    perms = cfg.get("permissions", {})
    if not isinstance(perms, dict):
        return "permissions debe ser un objeto"
    for key in ("allow", "ask", "deny", "additionalDirectories"):
        val = perms.get(key, [])
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            return f"permissions.{key} debe ser una lista de cadenas"
        for rule in val:
            if rule.count("(") != rule.count(")"):
                return f"regla mal formada: {rule}"
    hooks = cfg.get("hooks", {})
    if not isinstance(hooks, dict):
        return "hooks debe ser un objeto"
    for event, groups in hooks.items():
        if event not in HOOK_EVENTS:
            return f"evento de hook desconocido: {event}"
        if not isinstance(groups, list) or not all(isinstance(g, dict) and isinstance(g.get("hooks"), list) for g in groups):
            return f"hooks.{event} debe ser una lista de grupos con una lista `hooks`"
        for group in groups:
            for h in group["hooks"]:
                if not isinstance(h, dict) or h.get("type") not in {"command", "prompt", "agent", "http", "mcp_tool"}:
                    return f"hooks.{event}: tipo de hook invalido"
                if h["type"] == "command" and not isinstance(h.get("command"), str):
                    return f"hooks.{event}: un hook `command` necesita `command` (cadena)"
                if "shell" in h and h["shell"] not in ("bash", "powershell"):
                    return f"hooks.{event}: shell debe ser bash o powershell"
                if "timeout" in h and (isinstance(h["timeout"], bool) or not isinstance(h["timeout"], (int, float))):
                    return f"hooks.{event}: timeout debe ser un numero"
                if "onFailure" in h and h["onFailure"] not in ("continue", "block"):
                    return f"hooks.{event}: onFailure debe ser continue o block"
    if "disableAllHooks" in cfg and not isinstance(cfg["disableAllHooks"], bool):
        return "disableAllHooks debe ser booleano"
    return None


# ------------------------------------------------------------------ decision por herramienta
def decide_file(tool, ti, cwd):
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    rel = rel_path(path, cwd)
    cat = category(rel)
    if cat == "inbox":
        raise Deny("R1", f"`{path}` es un dato de entrada (data/inbox, deliveries): no se modifica nunca. "
                         "Los problemas de los datos se resuelven en el pipeline.")
    if cat == "code":
        code_gate()
    if rel in (".claude/settings.json", ".claude/settings.local.json"):
        if tool == "Write":
            new = ti.get("content", "")
        else:
            try:
                new = (PROJECT / rel).read_text(encoding="utf-8")
            except OSError:
                return
            for e in ti.get("edits") or [ti]:
                old, rep = e.get("old_string", ""), e.get("new_string", "")
                new = new.replace(old, rep) if e.get("replace_all") else new.replace(old, rep, 1)
        problem = check_settings(new)
        if problem:
            raise Deny("R6", f"el resultado dejaria {rel} invalido ({problem}); con un settings invalido NO queda en vigor "
                             "ninguna proteccion (ni hooks ni permisos).")


def decide_shell(ti, cwd):
    command = ti.get("command") or ""
    a = analyze(command, cwd)
    asks = []
    for rel in filter(None, a["writes"]):
        cat = category(rel)
        if cat == "inbox":
            raise Deny("R1", f"la orden escribe en `{rel}` (datos de entrada): no se modifican nunca. "
                             "Solo se incorporan con `tasks.py deliver N`.")
        if cat == "code":
            try:
                code_gate()
            except Ask as exc:
                asks.append(exc)
        if cat == "claude":
            asks.append(Ask("R6", f"la orden escribe en `{rel}` (configuracion del agente). ¿Confirmas?"))
    for code in a["pycode"]:
        if PY_WRITE.search(code) and re.search(r"data/inbox|deliveries", code.lower().replace("\\", "/")):
            raise Deny("R1", "el script escribe y menciona data/inbox o deliveries: los datos de entrada no se modifican.")
    adds = any(sub in ("add", "rm", "mv") for sub, _ in a["git"])
    for sub, rest in a["git"]:
        if sub == "commit" and "--amend" in rest:
            raise Deny("R2", "no se reescribe el historial: nada de `commit --amend`.")
        if sub == "rebase":
            raise Deny("R2", "no se reescribe el historial: nada de `rebase`.")
        if sub == "reset" and "--hard" in rest:
            raise Deny("R2", "`reset --hard` destruye trabajo: no se permite.")
        if sub in ("filter-branch", "filter-repo"):
            raise Deny("R2", "no se reescribe el historial.")
        if sub == "tag" and any(x in ("-d", "--delete", "-f", "--force") for x in rest):
            raise Deny("R2", "los tags phase-N no se borran ni se mueven.")
        if sub == "push":
            if any(x in ("-f", "--force", "--delete", "-d") or x.startswith(("--force-with-lease", "+", ":")) for x in rest):
                raise Deny("R2", "nada de push forzado ni de borrado de ramas o tags remotos.")
            positional = [x for x in rest if not x.startswith("-")]
            if positional and positional[0] != "origin":
                raise Deny("R2", f"solo se hace push a `origin` (no a `{positional[0]}`).")
        if sub == "commit":
            commit_gate(command, rest, adds)
    for n in a["deliver"]:
        deliver_gate(n)
    if asks:
        raise asks[0]


def decide(data):
    tool, ti = data.get("tool_name", ""), data.get("tool_input") or {}
    cwd = rel_path(data.get("cwd") or ROOT, "") if data.get("cwd") else ""
    if tool in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        decide_file(tool, ti, cwd)
    elif tool in ("Bash", "PowerShell"):
        decide_shell(ti, cwd)


def main():
    try:
        decide(json.loads(sys.stdin.buffer.read().decode("utf-8-sig")))
    except Deny as exc:
        sys.stderr.buffer.write((str(exc) + " No intentes eludirlo con otra orden.\n").encode("utf-8"))
        return 2
    except Ask as exc:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                 "permissionDecisionReason": str(exc)}}))
        return 0
    except Exception as exc:  # falla cerrado
        sys.stderr.buffer.write(f"BLOQUEADO [INTERNO]: error del guard ({exc!r}). {RECOVERY}\n".encode("utf-8"))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
