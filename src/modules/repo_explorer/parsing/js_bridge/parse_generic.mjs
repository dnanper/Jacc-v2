/**
 * Generic tree-sitter WASM parser bridge.
 *
 * Loads any WASM grammar and parses source code, outputting a JSON AST
 * for Python consumption. Replaces language-specific scripts with a
 * single reusable entry point.
 *
 * Usage:
 *   echo '<code>' | node parse_generic.mjs --wasm grammar.wasm --stdin name.ext
 *   node parse_generic.mjs --wasm grammar.wasm --file path/to/source.ext
 */

import { readFileSync } from "fs";
import { resolve } from "path";
import { Parser, Language } from "web-tree-sitter";

// ── Argument parsing ────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { wasm: null, file: null, stdin: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--wasm" && i + 1 < argv.length) {
      args.wasm = argv[++i];
    } else if (argv[i] === "--file" && i + 1 < argv.length) {
      args.file = argv[++i];
    } else if (argv[i] === "--stdin" && i + 1 < argv.length) {
      args.stdin = argv[++i];
    }
  }
  return args;
}

// ── AST Serialization ───────────────────────────────────────────────

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

  // Named fields — comprehensive set covering many grammars
  for (const fname of [
    "name", "modifiers", "parameters", "return_type", "type",
    "condition", "value", "target", "arguments",
    "object", "member", "left", "right", "inherits", "implements",
    "initializer", "label", "variable", "start", "end",
    "body", "receiver", "operator", "superclass", "interfaces",
    "type_parameters", "consequence", "alternative", "pattern",
    "module", "alias", "source", "path", "scope",
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

// ── Main ────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.wasm) {
    process.stderr.write(
      "Usage:\n" +
      "  node parse_generic.mjs --wasm grammar.wasm --file source.ext\n" +
      "  echo '<code>' | node parse_generic.mjs --wasm grammar.wasm --stdin name.ext\n"
    );
    process.exit(1);
  }

  let source, filePath;
  if (args.stdin) {
    filePath = args.stdin;
    const chunks = [];
    process.stdin.setEncoding("utf-8");
    for await (const chunk of process.stdin) chunks.push(chunk);
    source = chunks.join("");
  } else if (args.file) {
    filePath = args.file;
    source = readFileSync(filePath, "utf-8");
  } else {
    process.stderr.write("Error: must specify --file or --stdin\n");
    process.exit(1);
  }

  const wasmPath = resolve(args.wasm);

  await Parser.init();
  const parser = new Parser();
  const lang = await Language.load(wasmPath);
  parser.setLanguage(lang);

  const tree = parser.parse(source);

  const result = {
    filePath,
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
