/**
 * VB6 tree-sitter parser bridge (WASM via web-tree-sitter).
 *
 * Preprocesses VB6 source into VB.NET-compatible form, parses with
 * tree-sitter-vb-dotnet, and outputs a JSON AST for Python consumption.
 *
 * Usage:
 *   node parse_vb.mjs <file_path>                  # parse a file
 *   echo '<code>' | node parse_vb.mjs - name.bas   # parse stdin
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { Parser, Language } from "web-tree-sitter";

const __dirname = dirname(fileURLToPath(import.meta.url));
const WASM_PATH = resolve(__dirname, "tree-sitter-vb_dotnet.wasm");

// ── VB6 → VB.NET Preprocessing ──────────────────────────────────────

function preprocessVB6(source, filePath) {
  const ext = (filePath || "").toLowerCase();
  let code = source;

  // .frm: strip designer section (VERSION header + Begin...End blocks)
  if (ext.endsWith(".frm")) {
    const lines = code.split(/\r?\n/);
    let codeStart = 0;
    let depth = 0;
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (/^Begin\s+/i.test(trimmed)) depth++;
      if (/^End$/i.test(trimmed)) {
        depth--;
        if (depth <= 0) { codeStart = i + 1; depth = 0; }
      }
    }
    code = lines.slice(codeStart).join("\n");
  }

  // .cls: strip VERSION header and BEGIN...END property block
  if (ext.endsWith(".cls")) {
    const lines = code.split(/\r?\n/);
    let codeStart = 0;
    let inBlock = false;
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (/^BEGIN$/i.test(trimmed)) inBlock = true;
      if (inBlock && /^END$/i.test(trimmed)) {
        inBlock = false; codeStart = i + 1; continue;
      }
      if (/^VERSION\s+/i.test(trimmed)) { codeStart = i + 1; continue; }
    }
    code = lines.slice(codeStart).join("\n");
  }

  // Strip Attribute VB_Name etc (metadata, not code)
  code = code.split(/\r?\n/)
    .filter(l => !/^\s*Attribute\s+/i.test(l))
    .join("\n");

  // Patch VB6 syntax → VB.NET equivalents
  code = patchVB6Syntax(code);

  // Wrap in Module block (VB6 .bas/.frm/.cls have no explicit Module wrapper)
  if (ext.endsWith(".bas") || ext.endsWith(".frm") || ext.endsWith(".cls")) {
    const moduleName = (filePath || "Module1")
      .replace(/.*[/\\]/, "").replace(/\.[^.]+$/, "");
    code = `Module ${moduleName}\n${code}\nEnd Module\n`;
  }

  return code;
}

function patchVB6Syntax(code) {
  let p = code;
  // Type → Structure
  p = p.replace(/^(\s*)((?:Public|Private|Friend)\s+)?Type\s+(\w+)/gim, "$1$2Structure $3");
  p = p.replace(/^(\s*)End\s+Type\b/gim, "$1End Structure");
  // Set x = expr → x = expr
  p = p.replace(/^(\s*)Set\s+/gim, "$1");
  // Wend → End While
  p = p.replace(/^(\s*)Wend\b/gim, "$1End While");
  // On Error → comment (VB.NET uses Try/Catch)
  p = p.replace(/^(\s*)On\s+Error\s+(.*)/gim, "$1' [VB6] On Error $2");
  // Declare Function/Sub Name Lib ... → stub so name is captured as a symbol
  p = p.replace(/^(\s*)((?:Public|Private|Friend)\s+)?Declare\s+Function\s+(\w+)\b.*/gim,
    "$1$2Function $3()\nEnd Function ' [VB6-API]");
  p = p.replace(/^(\s*)((?:Public|Private|Friend)\s+)?Declare\s+Sub\s+(\w+)\b.*/gim,
    "$1$2Sub $3()\nEnd Sub ' [VB6-API]");
  // Option Explicit → Option Explicit On
  p = p.replace(/^(\s*)Option\s+Explicit\s*$/gim, "$1Option Explicit On");
  // Option Compare → comment
  p = p.replace(/^(\s*)Option\s+Compare\s+\w+\s*$/gim, "$1' Option Compare");
  // GoSub → comment
  p = p.replace(/^(\s*)GoSub\s+/gim, "$1' [VB6] GoSub ");
  // DefBool, DefByte etc → comment
  p = p.replace(/^(\s*)Def(Bool|Byte|Int|Lng|Cur|Sng|Dbl|Dec|Date|Str|Obj|Var)\s+/gim,
    "$1' [VB6] Def$2 ");
  return p;
}

// ── AST Serialization ────────────────────────────────────────────────

function serializeNode(node, depth) {
  if (depth > 60) return { type: "MAX_DEPTH", text: "" };
  const obj = {
    type: node.type,
    startPosition: { row: node.startPosition.row, column: node.startPosition.column },
    endPosition: { row: node.endPosition.row, column: node.endPosition.column },
    isNamed: node.isNamed,
    childCount: node.childCount,
    children: [],
    fields: {},
  };

  // Text: full for leaves/small nodes, truncated for large
  obj.text = (node.childCount === 0 || node.text.length < 300)
    ? node.text
    : node.text.slice(0, 80) + "...";

  for (let i = 0; i < node.childCount; i++) {
    obj.children.push(serializeNode(node.child(i), depth + 1));
  }

  // Named fields
  for (const fname of [
    "name", "modifiers", "parameters", "return_type", "type",
    "condition", "value", "target", "arguments",
    "object", "member", "left", "right", "inherits", "implements",
    "initializer", "label", "variable", "start", "end",
  ]) {
    const fnode = node.childForFieldName(fname);
    if (fnode) {
      obj.fields[fname] = {
        type: fnode.type,
        text: fnode.text.length < 300 ? fnode.text : fnode.text.slice(0, 80) + "...",
        startPosition: fnode.startPosition,
        endPosition: fnode.endPosition,
      };
    }
  }

  return obj;
}

// ── Main ─────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    process.stderr.write("Usage: node parse_vb.mjs <file_path | -> [name]\n");
    process.exit(1);
  }

  let source, filePath;
  if (args[0] === "-") {
    filePath = args[1] || "stdin.bas";
    const chunks = [];
    process.stdin.setEncoding("utf-8");
    for await (const chunk of process.stdin) chunks.push(chunk);
    source = chunks.join("");
  } else {
    filePath = args[0];
    source = readFileSync(filePath, "utf-8");
  }

  await Parser.init();
  const parser = new Parser();
  const lang = await Language.load(WASM_PATH);
  parser.setLanguage(lang);

  const processed = preprocessVB6(source, filePath);
  const tree = parser.parse(processed);

  const result = {
    filePath,
    preprocessedSource: processed,
    ast: serializeNode(tree.rootNode, 0),
    errors: [],
  };

  // Collect parse errors
  (function findErrors(node) {
    if (node.type === "ERROR" || node.isMissing) {
      result.errors.push({
        type: node.type,
        text: node.text.slice(0, 120),
        startPosition: node.startPosition,
        endPosition: node.endPosition,
      });
    }
    for (let i = 0; i < node.childCount; i++) findErrors(node.child(i));
  })(tree.rootNode);

  process.stdout.write(JSON.stringify(result) + "\n");
}

main().catch((err) => { process.stderr.write(String(err) + "\n"); process.exit(1); });
