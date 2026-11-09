"""Pruebas del hook kivora_guard. Se ejecutan con:  uv run python -m pytest .claude/hooks -q

Cada prueba llama al guard como lo hace Claude Code (JSON por stdin, CLAUDE_PROJECT_DIR apuntando a un
repositorio Git temporal) y comprueba el codigo de salida: 2 = bloqueado, 0 = permitido (con JSON `ask` si pide
confirmacion). La variable KIVORA_GUARD_UNDER_TEST permite probar una copia mutilada del guard y comprobar que
las pruebas fallan cuando una regla se rompe.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GUARD = Path(os.environ.get("KIVORA_GUARD_UNDER_TEST", HERE / "kivora_guard.py"))
REPO_ROOT = HERE.parents[1]
TRAILER = "Co-Authored-By: Claude Code <noreply@anthropic.com>"
COMMIT_OK = f'git commit -m "Fase 4: algo" -m "{TRAILER}"'


# ---------------------------------------------------------------- utilidades
def sh(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def commit_all(repo, msg):
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", msg)


_BASE = []


def _base_repo():
    """Repositorio base creado una sola vez; cada prueba trabaja sobre una copia (mucho mas rapido que re-crearlo)."""
    if not _BASE:
        import atexit
        import stat
        import tempfile
        base = Path(tempfile.mkdtemp(prefix="kivora-guard-base-"))
        repo = base / "repo"
        repo.mkdir()
        sh(repo, "init", "-q")
        for k, v in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            sh(repo, "config", k, v)
        write(repo, "README.md", "x\n")
        write(repo, "data/inbox/2026-09-01/orders.csv", "id\n1\n")
        write(repo, "deliveries/delivery-1/2026-09-04/orders.csv", "id\n4\n")
        commit_all(repo, "base")
        atexit.register(shutil.rmtree, base, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
        _BASE.append(repo)
    return _BASE[0]


def make_repo(tmp_path, tags=(), plan=False, impact=False, spec102=False):
    repo = tmp_path / "repo"
    shutil.copytree(_base_repo(), repo)
    if plan:
        write(repo, "docs/specs/KIV-101/spec.md", "spec\n")
        write(repo, "docs/specs/KIV-101/plan.md", "borrador\n")
        commit_all(repo, "borrador")
        write(repo, "docs/specs/KIV-101/plan.md", "borrador\n## Revisión del plan\n")
        commit_all(repo, "revision")
    if impact:
        write(repo, "docs/specs/KIV-102/impact.md", "impacto\n")
        commit_all(repo, "impacto")
    if spec102:
        write(repo, "docs/specs/KIV-102/spec.md", "s\n")
        write(repo, "docs/specs/KIV-102/plan.md", "p\n")
        commit_all(repo, "spec102")
    for t in tags:
        sh(repo, "tag", t)
    return repo


def run(repo, tool, **tool_input):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": str(repo)}
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    p = subprocess.run([sys.executable, "-I", str(GUARD)], input=json.dumps(payload).encode("utf-8"),
                       capture_output=True, env=env)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def assert_blocked(result, rule):
    code, _, err = result
    assert code == 2 and f"[{rule}]" in err, result


def assert_allowed(result):
    code, out, err = result
    assert code == 0 and out.strip() == "" and err.strip() == "", result


def assert_ask(result, rule):
    code, out, _ = result
    assert code == 0 and '"permissionDecision": "ask"' in out and f"[{rule}]" in out, result


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


# ---------------------------------------------------------------- R1: datos de entrada
def test_r1_las_herramientas_de_edicion_no_tocan_los_datos(repo):
    for rel in ("data/inbox/2026-09-01/orders.csv", "deliveries/delivery-1/2026-09-04/orders.csv"):
        assert_blocked(run(repo, "Write", file_path=str(repo / rel), content="x"), "R1")
    assert_blocked(run(repo, "Edit", file_path=str(repo / "data/inbox/2026-09-01/orders.csv"),
                       old_string="id", new_string="ID"), "R1")


@pytest.mark.parametrize("tool,command", [
    ("PowerShell", r"Set-Content data\inbox\2026-09-01\orders.csv 'x'"),
    ("Bash", "echo x >> data/inbox/2026-09-01/orders.csv"),
    ("Bash", "cd data/inbox && touch nuevo.txt"),
    ("Bash", "git checkout -- data/inbox/2026-09-01/orders.csv"),
    ("Bash", "uv run python -c \"open('data/inbox/2026-09-01/orders.csv','w').write('x')\""),
])
def test_r1_las_escrituras_por_shell_se_bloquean(repo, tool, command):
    assert_blocked(run(repo, tool, command=command), "R1")


@pytest.mark.parametrize("tool,command", [
    ("PowerShell", r"Get-Content data\inbox\2026-09-01\orders.csv | Select-Object -First 3"),
    ("PowerShell", r"Copy-Item data\inbox\2026-09-01\orders.csv C:\tmp\copia.csv"),
    ("Bash", "git add data/inbox/2026-09-04"),
    ("Bash", "uv run python -m kivora --inbox data/inbox --reference data/reference --out output 2>&1"),
])
def test_r1_las_lecturas_y_el_pipeline_se_permiten(repo, tool, command):
    assert_allowed(run(repo, tool, command=command))


# ---------------------------------------------------------------- R2: historial
@pytest.mark.parametrize("tool,command", [
    ("Bash", "git commit --amend --no-edit"),
    ("Bash", "git reset --hard HEAD~1"),
    ("Bash", "git -C . push -f origin master"),
    ("PowerShell", "git push origin master --force-with-lease"),
    ("Bash", "git push upstream master"),
    ("Bash", "git tag -d phase-2"),
])
def test_r2_no_se_reescribe_el_historial(repo, tool, command):
    assert_blocked(run(repo, tool, command=command), "R2")


@pytest.mark.parametrize("command", ["git push origin master", 'git tag -a phase-3 -m "Fase 3"'])
def test_r2_las_operaciones_normales_pasan(repo, command):
    assert_allowed(run(repo, "Bash", command=command))


# ---------------------------------------------------------------- R3: puerta del commit
def test_r3_el_commit_exige_el_trailer_co_authored_by(repo):
    write(repo, "docs/a.md", "a\n")
    sh(repo, "add", "docs/a.md")
    assert_blocked(run(repo, "Bash", command='git commit -m "Fase 4: algo"'), "R3")
    assert_allowed(run(repo, "Bash", command=COMMIT_OK))
    assert_allowed(run(repo, "PowerShell", command="git commit -m @'\nFase 4: algo\n\n" + TRAILER + "\n'@"))


@pytest.mark.parametrize("command", [
    f'git add docs/a.md && git commit -m "x" -m "{TRAILER}"',
    f'git commit -am "x" -m "{TRAILER}"',
])
def test_r3_commit_separado_y_sin_a(repo, command):
    assert_blocked(run(repo, "Bash", command=command), "R3")


@pytest.mark.parametrize("rel", ["sesion.jsonl", ".env"])
def test_r3_no_entran_transcripciones_secretos_ni_salidas(repo, rel):
    write(repo, rel, "x\n")
    sh(repo, "add", "-f", rel)
    assert_blocked(run(repo, "Bash", command=COMMIT_OK), "R3")


def test_r3_las_entregas_solo_se_anaden_y_coinciden_con_deliveries(repo):
    write(repo, "data/inbox/2026-09-04/orders.csv", "id\n4\n")  # identico a deliveries/delivery-1
    sh(repo, "add", "data/inbox/2026-09-04/orders.csv")
    assert_allowed(run(repo, "Bash", command=COMMIT_OK))
    write(repo, "data/inbox/2026-09-04/orders.csv", "id\nOTRO\n")  # distinto
    sh(repo, "add", "data/inbox/2026-09-04/orders.csv")
    assert_blocked(run(repo, "Bash", command=COMMIT_OK), "R3")
    sh(repo, "reset", "-q")
    write(repo, "data/inbox/2026-09-01/orders.csv", "id\nMODIFICADO\n")  # entrega existente modificada
    sh(repo, "add", "data/inbox/2026-09-01/orders.csv")
    assert_blocked(run(repo, "Bash", command=COMMIT_OK), "R3")


def test_r3_la_entrega_va_en_un_commit_propio(repo):
    write(repo, "data/inbox/2026-09-04/orders.csv", "id\n4\n")
    write(repo, "docs/otra-cosa.md", "x\n")
    sh(repo, "add", "data/inbox/2026-09-04/orders.csv", "docs/otra-cosa.md")
    assert_blocked(run(repo, "Bash", command=COMMIT_OK), "R3")


def test_r3_espacios_sobrantes_bloquean_salvo_en_las_sesiones_exportadas(repo):
    write(repo, "docs/a.md", "linea con espacios   \n")
    sh(repo, "add", "docs/a.md")
    assert_blocked(run(repo, "Bash", command=COMMIT_OK), "R3")
    sh(repo, "reset", "-q")
    write(repo, "docs/sessions/fase-2.md", "export sin editar   \n")
    sh(repo, "add", "docs/sessions/fase-2.md")
    assert_allowed(run(repo, "Bash", command=COMMIT_OK))


# ---------------------------------------------------------------- R4: orden de fases
CODE = "kivora/pipeline.py"


def test_r4_por_fases_y_artefactos(tmp_path):
    t3, t4 = ("phase-1", "phase-2", "phase-3"), ("phase-1", "phase-2", "phase-3", "phase-4")
    cases = [
        (dict(tags=("phase-1", "phase-2")), "ask"),                                  # fase 3: configuracion del agente
        (dict(tags=t3), "deny"),                                                     # fase 4 sin spec/plan revisado
        (dict(tags=t3, plan=True), "allow"),                                         # fase 4 con spec + plan revisado
        (dict(tags=t4, plan=True), "deny"),                                          # fase 5 sin impacto
        (dict(tags=t4, plan=True, impact=True, spec102=True), "allow"),              # fase 5 con impacto, spec y plan
    ]
    for i, (kw, expected) in enumerate(cases):
        r = make_repo(tmp_path / f"c{i}", **kw)
        res = run(r, "Write", file_path=str(r / CODE), content="x")
        if expected == "deny":
            assert_blocked(res, "R4")
        elif expected == "ask":
            assert_ask(res, "R4")
        else:
            assert_allowed(res)
    shell_repo = make_repo(tmp_path / "shell", tags=t3)  # el mismo gate rige tambien las escrituras por shell
    assert_blocked(run(shell_repo, "Bash", command="echo x > tests/test_x.py"), "R4")


def test_r4_la_documentacion_se_edita_siempre(repo):
    assert_allowed(run(repo, "Write", file_path=str(repo / "docs/report.md"), content="x"))


# ---------------------------------------------------------------- R5: entregas en su fase
def test_r5_deliver_solo_en_su_fase(tmp_path):
    r = make_repo(tmp_path / "a")
    assert_blocked(run(r, "Bash", command="uv run python tasks.py deliver 2"), "R5")
    assert_blocked(run(r, "PowerShell", command="uv run python tasks.py deliver 1"), "R5")  # sin phase-1
    r1 = make_repo(tmp_path / "b", tags=("phase-1",))
    assert_allowed(run(r1, "Bash", command="uv run python tasks.py deliver 1"))
    assert_blocked(run(r1, "Bash", command="uv run python tasks.py deliver 2"), "R5")
    r4 = make_repo(tmp_path / "c", tags=("phase-1", "phase-2", "phase-3", "phase-4"))
    assert_blocked(run(r4, "Bash", command="uv run python tasks.py deliver 2"), "R5")  # falta la entrega 1
    write(r4, "docs/tickets/KIV-101.md", "t\n")
    write(r4, "data/inbox/2026-09-07/orders.csv", "x\n")
    assert_allowed(run(r4, "Bash", command="uv run python tasks.py deliver 2"))


# ---------------------------------------------------------------- R6: settings invalido = sin protecciones
def test_r6_no_se_escribe_un_settings_invalido(repo):
    target = str(repo / ".claude/settings.json")
    assert_blocked(run(repo, "Write", file_path=target, content='{ "permissions": { "deny": ["x",] } }'), "R6")
    assert_blocked(run(repo, "Write", file_path=target, content='{ "permissions": { "allow": "Bash(echo *)" } }'), "R6")
    assert_blocked(run(repo, "Write", file_path=target, content='{ "hooks": { "PreToolUsee": [] } }'), "R6")
    assert_allowed(run(repo, "Write", file_path=target, content='{ "permissions": { "deny": ["Bash(git push --force *)"] } }'))
    write(repo, ".claude/settings.json", '{ "permissions": { "deny": ["a"] } }')
    assert_blocked(run(repo, "Edit", file_path=target, old_string='["a"]', new_string='["a",]'), "R6")


def test_r6_escribir_en_claude_por_shell_pide_confirmacion(repo):
    assert_ask(run(repo, "PowerShell", command="Set-Content .claude/settings.json '{}'"), "R6")


# ---------------------------------------------------------------- falla cerrado y configuracion real
def test_falla_cerrado_ante_una_entrada_ilegible(repo):
    p = subprocess.run([sys.executable, "-I", str(GUARD)], input=b"esto no es json", capture_output=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)})
    assert p.returncode == 2 and b"[INTERNO]" in p.stderr


def _guard_module():
    spec = importlib.util.spec_from_file_location("kivora_guard_under_test", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_la_configuracion_real_del_proyecto_es_valida_y_registra_el_hook():
    text = (REPO_ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    assert _guard_module().check_settings(text) is None
    cfg = json.loads(text)
    hook = cfg["hooks"]["PreToolUse"][0]["hooks"][0]
    assert "kivora_guard.py" in hook["command"] and hook["onFailure"] == "block"
    for tool in ("Bash", "PowerShell", "Edit", "Write"):
        assert tool in cfg["hooks"]["PreToolUse"][0]["matcher"]
    assert "Edit(/data/inbox/**)" in cfg["permissions"]["deny"]
    assert "Bash(git commit *)" in cfg["permissions"]["ask"]


@pytest.mark.skipif(shutil.which("claude") is None, reason="la CLI claude no esta disponible")
def test_claude_doctor_no_reporta_settings_invalidos():
    out = subprocess.run(["claude", "doctor"], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=90).stdout
    assert "Invalid settings" not in out, out
