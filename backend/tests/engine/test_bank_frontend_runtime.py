"""Сверка ключей frontend-шаблонов с настоящими системами.

- JS code_output и == — запуск сгенерированного кода в node;
- DOM-события — jsdom (реализация спецификации DOM);
- React — настоящий React 18.3 + react-dom в jsdom (JSX через sucrase);
- TypeScript — компилятор tsc (strict).

Для jsdom/React/TS нужны npm-пакеты: jsdom@24 react@18.3.1 react-dom@18.3.1 sucrase
typescript@5. Папка с node_modules берётся из переменной FRONTEND_JS_TOOLS или ищется
выше по дереву в `_волны/tmp/*/frontend/js`. Нет node или пакетов — тест пропускается.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.testing.engine.bank.frontend import TEMPLATES
from app.testing.engine.templates import ItemFormat, ItemInstance, check

BY_ID = {t.id: t for t in TEMPLATES}
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node не установлен")


def _find_tools() -> Path | None:
    env = os.environ.get("FRONTEND_JS_TOOLS")
    if env:
        p = Path(env)
        return p if (p / "node_modules").is_dir() else None
    for parent in Path(__file__).resolve().parents:
        tmp = parent / "_волны" / "tmp"
        if tmp.is_dir():
            for cand in sorted(tmp.glob("*/frontend/js")):
                if (cand / "node_modules" / "jsdom").is_dir():
                    return cand
    return None


TOOLS = _find_tools()


def _has(pkg: str) -> bool:
    return TOOLS is not None and (TOOLS / "node_modules" / pkg).is_dir()


needs_jsdom = pytest.mark.skipif(NODE is None or not _has("jsdom"), reason="нет node/jsdom")
needs_react = pytest.mark.skipif(
    NODE is None or not all(_has(p) for p in ("react", "react-dom", "jsdom", "sucrase")),
    reason="нет node/react/react-dom/jsdom/sucrase",
)
needs_ts = pytest.mark.skipif(NODE is None or not _has("typescript"), reason="нет typescript")


def _run_node_script(tmp_path: Path, script: str, payload: object) -> list[dict[str, object]]:
    path = tmp_path / "harness.js"
    path.write_text(script, encoding="utf-8")
    assert NODE is not None
    out = subprocess.run(
        [NODE, str(path), str(TOOLS)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    result: list[dict[str, object]] = json.loads(out.stdout)
    return result


# --------------------------------------------------------------------------- node: чистый JS

NODE_TEMPLATES = [
    "frontend.js_coercion",
    "frontend.js_array_methods",
    "frontend.js_closures_loop",
    "frontend.js_object_copy",
    "frontend.js_this_binding",
    "frontend.js_promise_chain",
    "frontend.js_promise_combinators",
]


@needs_node
@pytest.mark.parametrize("tid", NODE_TEMPLATES)
def test_js_output_matches_node(tid: str) -> None:
    t = BY_ID[tid]
    assert t.format is ItemFormat.CODE_OUTPUT
    for seed in range(30):
        inst = t.generate(seed)
        assert NODE is not None and inst.public.code
        out = subprocess.run(
            [NODE, "-e", inst.public.code], capture_output=True, text=True, timeout=30
        )
        assert out.returncode == 0, (seed, out.stderr)
        assert check(inst, out.stdout), (seed, inst.public.code, out.stdout, inst.key)


@needs_node
def test_loose_equality_matches_node() -> None:
    t = BY_ID["frontend.js_loose_equality"]
    for seed in range(40):
        inst = t.generate(seed)
        exprs = list(inst.public.options)
        script = "console.log(JSON.stringify([" + ", ".join(f"({e})" for e in exprs) + "]));"
        assert NODE is not None
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        values = json.loads(out.stdout)
        assert frozenset(i for i, v in enumerate(values) if v is True) == inst.key, exprs


# --------------------------------------------------------------------------- jsdom: DOM-события

DOM_HARNESS = r"""
const path = require('path');
const { JSDOM, VirtualConsole } = require(path.join(process.argv[2], 'node_modules', 'jsdom'));
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = [];
for (const code of input) {
  const [htmlPart, jsPart] = code.split('\n\n// JS\n');
  const html = htmlPart.replace('<!-- HTML -->\n', '');
  const logs = [];
  const vc = new VirtualConsole();
  vc.on('log', (...a) => logs.push(a.map(String).join(' ')));
  vc.on('jsdomError', (e) => logs.push('JSDOM_ERROR ' + e.message));
  const dom = new JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'outside-only', virtualConsole: vc,
  });
  try { dom.window.eval(jsPart); } catch (e) { logs.push('ERROR ' + e.message); }
  out.push({ logs });
}
process.stdout.write(JSON.stringify(out));
"""


@needs_jsdom
@pytest.mark.parametrize(
    "tid",
    [
        "frontend.dom_target_delegation",
        "frontend.dom_event_phases",
        "frontend.dom_stop_propagation",
    ],
)
def test_dom_events_match_jsdom(tid: str, tmp_path: Path) -> None:
    t = BY_ID[tid]
    insts = [t.generate(seed) for seed in range(40)]
    res = _run_node_script(tmp_path, DOM_HARNESS, [i.public.code for i in insts])
    for seed, (inst, r) in enumerate(zip(insts, res, strict=True)):
        logs = r["logs"]
        assert isinstance(logs, list)
        assert not any(str(x).startswith(("ERROR", "JSDOM_ERROR")) for x in logs), logs
        if t.format is ItemFormat.ORDERING:
            expected = [inst.public.options[k] for k in inst.key]
            assert logs == expected, (seed, inst.public.code, logs, expected)
        else:
            assert check(inst, " ".join(map(str, logs))), (seed, inst.public.code, logs, inst.key)


# --------------------------------------------------------------------------- React 18

REACT_HARNESS = r"""
const path = require('path');
const req = (m) => require(path.join(process.argv[2], 'node_modules', m));
const { JSDOM } = req('jsdom');
const sucrase = req('sucrase');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.HTMLElement = dom.window.HTMLElement;
global.IS_REACT_ACT_ENVIRONMENT = true;
const React = req('react');
const { createRoot } = req('react-dom/client');
const { act } = req('react-dom/test-utils');
const origLog = console.log;
console.error = () => {};
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const results = [];
for (const c of input) {
  const logs = [];
  let root = null;
  const container = document.createElement('div');
  document.body.appendChild(container);
  try {
    const js = sucrase.transform(c.code, {
      transforms: ['jsx', 'imports'], jsxRuntime: 'automatic', production: true,
    }).code;
    const m = { exports: {} };
    new Function('require', 'module', 'exports', js)(req, m, m.exports);
    console.log = (...a) => logs.push(a.join(' '));
    root = createRoot(container);
    act(() => root.render(React.createElement(m.exports.default)));
    for (const step of c.steps) {
      if (step.clear) logs.length = 0;
      if (step.type) {
        const inputs = container.querySelectorAll('input');
        step.type.forEach((t, i) => { inputs[i].value = t; });
      }
      if (step.click) {
        const btn = [...container.querySelectorAll('button')].find(
          (b) => step.click === '*' || b.textContent === step.click);
        for (let i = 0; i < (step.times || 1); i++) {
          act(() => { btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
        }
      }
    }
    const rows = [...container.querySelectorAll('p')].map((p) => {
      const inp = p.querySelector('input');
      return p.textContent.split(':')[0].trim() + '=' + (inp ? inp.value : '');
    });
    const b = container.querySelector('button');
    results.push({ logs: [...logs], button: b ? b.textContent : null, rows });
  } catch (e) {
    results.push({ error: String((e && e.stack) || e) });
  }
  console.log = () => {};
  try { act(() => root && root.unmount()); } catch (e) {}
  console.log = origLog;
  container.remove();
}
process.stdout.write(JSON.stringify(results));
"""


def _react_steps(inst: ItemInstance) -> list[dict[str, object]]:
    tid = inst.template_id
    prompt = inst.public.prompt
    if tid == "frontend.react_state_batching":
        return [{"click": "*", "times": 1 if "один раз" in prompt else 2}]
    if tid == "frontend.react_list_keys":
        return [{"type": re.findall(r"«([a-z]+)»", prompt)}, {"click": "Изменить"}]
    if tid == "frontend.react_memo_renders":
        m = re.search(r"«\+1» (\d+)", prompt)
        assert m
        return [{"click": "+1", "times": int(m.group(1))}]
    if "монтировании" in prompt:
        return []
    return [{"clear": True}, {"click": "+1"}]


def _react_ok(inst: ItemInstance, r: dict[str, object]) -> bool:
    tid = inst.template_id
    logs = r["logs"]
    assert isinstance(logs, list)
    if tid == "frontend.react_state_batching":
        return float(str(r["button"])) == inst.key.value
    if tid == "frontend.react_list_keys":
        rows = r["rows"]
        assert isinstance(rows, list)
        return check(inst, " ".join(rows))
    if tid == "frontend.react_memo_renders":
        return logs.count("render Child") == inst.key.value
    return logs == [inst.public.options[k] for k in inst.key]


@needs_react
@pytest.mark.parametrize(
    "tid",
    [
        "frontend.react_state_batching",
        "frontend.react_list_keys",
        "frontend.react_memo_renders",
        "frontend.react_effect_order",
    ],
)
def test_react_answers_match_real_react(tid: str, tmp_path: Path) -> None:
    t = BY_ID[tid]
    insts = [t.generate(seed) for seed in range(40)]
    payload = [{"code": i.public.code, "steps": _react_steps(i)} for i in insts]
    res = _run_node_script(tmp_path, REACT_HARNESS, payload)
    for seed, (inst, r) in enumerate(zip(insts, res, strict=True)):
        assert "error" not in r, (seed, r.get("error"), inst.public.code)
        assert _react_ok(inst, r), (seed, inst.public.prompt, inst.public.code, r, inst.key)


@needs_react
def test_hook_answers_are_real_react_exports() -> None:
    t = BY_ID["frontend.react_hook_choice"]
    answers = {t.generate(seed).key[0] for seed in range(300)}
    assert NODE is not None and TOOLS is not None
    react_path = (TOOLS / "node_modules" / "react").as_posix()
    out = subprocess.run(
        [NODE, "-e", f"console.log(JSON.stringify(Object.keys(require('{react_path}'))))"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    exports = set(json.loads(out.stdout))
    assert answers <= exports, answers - exports
    assert len(answers) >= 8


# --------------------------------------------------------------------------- TypeScript

TS_HARNESS = r"""
const path = require('path');
const fs = require('fs');
const os = require('os');
const ts = require(path.join(process.argv[2], 'node_modules', 'typescript'));
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tsbank-'));
const files = input.map((code, i) => {
  const f = path.join(dir, 'case' + i + '.ts');
  fs.writeFileSync(f, code + '\nexport {};\n');
  return f;
});
const program = ts.createProgram(files, {
  strict: true, noEmit: true, target: ts.ScriptTarget.ES2022,
  lib: ['lib.es2022.d.ts', 'lib.dom.d.ts'], skipLibCheck: true,
});
const checker = program.getTypeChecker();
const out = files.map((f) => {
  const sf = program.getSourceFile(f);
  const diags = [...program.getSyntacticDiagnostics(sf), ...program.getSemanticDiagnostics(sf)];
  const lines = diags.map((d) => sf.getLineAndCharacterOfPosition(d.start).line + 1);
  let typeR = null;
  ts.forEachChild(sf, (node) => {
    if (ts.isTypeAliasDeclaration(node) && node.name.text === 'R') {
      const t = checker.getTypeAtLocation(node.name);
      const flags = ts.TypeFormatFlags.NoTruncation | ts.TypeFormatFlags.InTypeAlias;
      // keyof X печатается как "keyof X" — раскрываем объединение по членам
      typeR = t.isUnion() && !(t.flags & ts.TypeFlags.Boolean)
        ? t.types.map((m) => checker.typeToString(m, undefined, flags)).join(' | ')
        : checker.typeToString(t, undefined, flags);
    }
  });
  const messages = diags.map((d) => ts.flattenDiagnosticMessageText(d.messageText, ' '));
  return { lines, typeR, messages };
});
process.stdout.write(JSON.stringify(out));
"""


def _split_top(text: str, sep: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for i, ch in enumerate(text):
        if ch in "([<{":
            depth += 1
        elif ch in ")]}" or (ch == ">" and text[i - 1] != "="):
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return parts


def _canon_member(m: str) -> str:
    if m and m[0] in "([":
        close = {"(": ")", "[": "]"}[m[0]]
        depth = 0
        for j, ch in enumerate(m):
            depth += ch == m[0]
            depth -= ch == close
            if depth == 0:
                inner = ", ".join(_canon(x) for x in _split_top(m[1:j], ","))
                return m[0] + inner + close + m[j + 1 :]
    if "<" in m and m.endswith(">") and not m.startswith("("):
        name, args = m.split("<", 1)
        return name + "<" + ", ".join(_canon(a) for a in _split_top(args[:-1], ",")) + ">"
    return m


def _canon(type_text: str) -> str:
    members = sorted(_canon_member(p.replace("'", '"')) for p in _split_top(type_text, "|"))
    return " | ".join(members)


def _union_members(type_text: str) -> str:
    """Каноническая запись типа: члены объединений отсортированы на всех уровнях."""
    return _canon(type_text.strip())


@needs_ts
def test_ts_compile_error_line_matches_tsc(tmp_path: Path) -> None:
    t = BY_ID["frontend.ts_compile_error"]
    insts = [t.generate(seed) for seed in range(80)]
    res = _run_node_script(tmp_path, TS_HARNESS, [i.public.code for i in insts])
    for seed, (inst, r) in enumerate(zip(insts, res, strict=True)):
        lines = r["lines"]
        assert isinstance(lines, list)
        assert sorted(set(lines)) == [inst.key], (seed, inst.public.code, r)


@needs_ts
def test_ts_conditional_type_matches_tsc(tmp_path: Path) -> None:
    t = BY_ID["frontend.ts_conditional_types"]
    insts = [t.generate(seed) for seed in range(80)]
    res = _run_node_script(tmp_path, TS_HARNESS, [i.public.code for i in insts])
    for seed, (inst, r) in enumerate(zip(insts, res, strict=True)):
        assert r["lines"] == [], (seed, inst.public.code, r)
        actual = _union_members(str(r["typeR"]))
        options = [_union_members(o) for o in inst.public.options]
        assert options[inst.key] == actual, (seed, inst.public.code, r["typeR"])
        assert sum(o == actual for o in options) == 1, (seed, inst.public.options)
