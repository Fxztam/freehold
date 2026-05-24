function splitLineComment(line) {
    let inString = false;
    let escaped = false;
    for (let i = 0; i < line.length - 1; i++) {
        const ch = line[i];
        if (escaped) { escaped = false; continue; }
        if (ch === '\\' && inString) { escaped = true; continue; }
        if (ch === '"') { inString = !inString; continue; }
        if (!inString && line[i] === '-' && line[i + 1] === '-') {
            return { code: line.slice(0, i), comment: line.slice(i).trimEnd() };
        }
    }
    return { code: line, comment: '' };
}

function normalizeSpaces(code) {
    let s = code.trim();
    if (!s) return '';

    const strings = [];
    s = s.replace(/"(?:\\.|[^"\\])*"/g, (m) => {
        const key = `__FH_STRING_${strings.length}__`;
        strings.push(m);
        return key;
    });

    const ops = [];
    s = s.replace(/(:=|=>|<=|>=|!=|\.\.)/g, (m) => {
        const key = `__FH_OP_${ops.length}__`;
        ops.push(m);
        return key;
    });

    s = s.replace(/\s*([+\-*\/=<>])\s*/g, ' $1 ');
    s = s.replace(/\s*,\s*/g, ', ');
    s = s.replace(/\s*:\s*/g, ': ');
    s = s.replace(/\s*\.\s*/g, '.');
    s = s.replace(/\(\s+/g, '(').replace(/\s+\)/g, ')');
    s = s.replace(/\[\s+/g, '[').replace(/\s+\]/g, ']');
    s = s.replace(/\{\s*/g, '{ ').replace(/\s*\}/g, ' }');
    s = s.replace(/\s+/g, ' ').trim();

    ops.forEach((value, i) => {
        s = s.replace(`__FH_OP_${i}__`, ` ${value} `);
    });

    s = s.replace(/\b(Set|Array|Result|JoinHandle|Channel|Sender|Receiver)\s*<\s*/g, '$1<');
    s = s.replace(/\b(Set|Array|Result|JoinHandle|Channel|Sender|Receiver)<([^>]*)\s*>/g, (_m, name, inner) => `${name}<${inner.trim()}>`);
    s = s.replace(/(<[^>]+>)\s*=/g, '$1 =');
    s = s.replace(/(<[^>]+>)\s*:=/g, '$1 :=');
    s = s.replace(/\s+/g, ' ').trim();

    strings.forEach((value, i) => {
        s = s.replace(`__FH_STRING_${i}__`, value);
    });
    return s;
}

function startsWithDedentKeyword(code) {
    const s = code.trim();
    return /^(end\b|else\b|default\b|when\b|join\b|result\b)/.test(s);
}

function increasesIndentAfter(code) {
    const s = code.trim();
    if (/^module\b/.test(s)) return false;
    if (/^import\b/.test(s)) return false;
    if (/^end\b/.test(s)) return false;
    if (/^when\b.*=>\s*$/.test(s)) return true;
    if (/^default\b.*=>\s*$/.test(s)) return true;
    if (/^(spawn|join|result)\b/.test(s)) return true;
    return /\bis\s*$/.test(s) || /\bthen\s*$/.test(s) || /\bdo\s*$/.test(s) || /\brecord\s*$/.test(s) || /^else\b/.test(s);
}

function isBlockCommentStart(s) { return s.includes('/*'); }
function isBlockCommentEnd(s) { return s.includes('*/'); }

const KEYWORD_COMPLETIONS = [
    'module', 'import', 'exposing', 'type', 'record', 'error', 'service', 'rpc', 'proto',
    'function', 'procedure', 'async', 'returns', 'is', 'end', 'let', 'call', 'return',
    'ok', 'abort', 'requires', 'ensures', 'aborts', 'if', 'then', 'else', 'while',
    'do', 'invariant', 'variant', 'case', 'when', 'default', 'check', 'scope',
    'spawn', 'join', 'result', 'await', 'true', 'false', 'success', 'failure', 'value'
];

const TYPE_COMPLETIONS = [
    'Integer', 'Boolean', 'Double', 'String', 'BigInteger', 'BigFloat',
    'Array', 'Result', 'Executor', 'Scope', 'JoinHandle', 'Channel', 'Sender', 'Receiver'
];

const BUILTIN_COMPLETIONS = [
    'String.concat', 'String.substr', 'String.replace', 'String.instr',
    'Math.abs', 'Math.sqrt', 'Math.pow', 'Math.floor', 'Math.ceil', 'Math.min', 'Math.max',
    'Json.stringify', 'Std.IO.log', 'Std.IO.logf', 'Std.IO.log_int', 'Std.IO.log_bool', 'Std.IO.log_double',
    'scope', 'scope_spawn', 'scope_join', 'channel', 'channel_sender', 'channel_receiver', 'channel_send', 'channel_receive'
];

const SNIPPET_COMPLETIONS = [
    {
        label: 'module block',
        insertText: 'module ${1:Module.Name}\n\n$0\nend ${1:Module.Name}',
        detail: 'Freehold module block'
    },
    {
        label: 'record type',
        insertText: 'type ${1:Name} is record\n    ${2:field}: ${3:String} proto ${4:1}\nend record',
        detail: 'Record type with proto field id'
    },
    {
        label: 'function',
        insertText: 'function ${1:name}(${2}) returns ${3:Integer}\nis\n    ${0:return 0}\nend ${1:name}',
        detail: 'Function declaration'
    },
    {
        label: 'procedure',
        insertText: 'procedure ${1:name}(${2})\nis\n    $0\nend ${1:name}',
        detail: 'Procedure declaration'
    },
    {
        label: 'service rpc',
        insertText: 'service ${1:NameService} is\n    rpc ${2:Call}(request: ${3:Request}): ${4:Reply}\nend ${1:NameService}',
        detail: 'gRPC service with unary rpc'
    },
    {
        label: 'if then',
        insertText: 'if ${1:condition} then\n    $0\nend if',
        detail: 'If statement'
    },
    {
        label: 'case default',
        insertText: 'case ${1:value} is\n    when ${2:match} =>\n        $0\n    default =>\n        ${3:check false}\nend case',
        detail: 'Case statement with default branch'
    },
    {
        label: 'scope block',
        insertText: 'scope ${1:s} do\nspawn\n    $0\njoin\nresult\nend scope',
        detail: 'Structured concurrency scope block'
    },
    {
        label: 'return ok',
        insertText: 'return ok ${1:value}',
        detail: 'Result success return'
    },
    {
        label: 'return error',
        insertText: 'return error ${1:ErrorName}',
        detail: 'Result error return'
    }
];

function completionEntries() {
    return [
        ...KEYWORD_COMPLETIONS.map(label => ({ label, kind: 'keyword', insertText: label })),
        ...TYPE_COMPLETIONS.map(label => ({ label, kind: 'type', insertText: label })),
        ...BUILTIN_COMPLETIONS.map(label => ({ label, kind: 'function', insertText: label })),
        ...SNIPPET_COMPLETIONS.map(item => ({ ...item, kind: 'snippet' }))
    ];
}

function createCompletionItems(vscode) {
    const kindMap = {
        keyword: vscode.CompletionItemKind.Keyword,
        type: vscode.CompletionItemKind.Class,
        function: vscode.CompletionItemKind.Function,
        snippet: vscode.CompletionItemKind.Snippet
    };
    return completionEntries().map(entry => {
        const item = new vscode.CompletionItem(entry.label, kindMap[entry.kind] || vscode.CompletionItemKind.Text);
        item.detail = entry.detail || `Freehold ${entry.kind}`;
        item.insertText = entry.kind === 'snippet'
            ? new vscode.SnippetString(entry.insertText)
            : entry.insertText;
        return item;
    });
}

function formatFreehold(text, indentSize = 4) {
    const lines = text.replace(/\r\n/g, '\n').split('\n');
    const out = [];
    let indent = 0;
    const unit = ' '.repeat(indentSize);
    let inBlockComment = false;

    for (const raw of lines) {
        const trimmed = raw.trim();
        if (trimmed.length === 0) {
            if (out.length > 0 && out[out.length - 1] !== '') out.push('');
            continue;
        }

        if (inBlockComment) {
            out.push(unit.repeat(indent) + trimmed);
            if (isBlockCommentEnd(trimmed)) inBlockComment = false;
            continue;
        }

        if (trimmed.startsWith('/*')) {
            out.push(unit.repeat(indent) + trimmed);
            if (!isBlockCommentEnd(trimmed)) inBlockComment = true;
            continue;
        }

        const { code, comment } = splitLineComment(trimmed);
        const normalized = normalizeSpaces(code);
        const onlyComment = normalized.length === 0 && comment.length > 0;

        if (!onlyComment && startsWithDedentKeyword(normalized)) indent = Math.max(0, indent - 1);

        let line = onlyComment ? unit.repeat(indent) + comment : unit.repeat(indent) + normalized;
        if (!onlyComment && comment) line += ' ' + comment;
        out.push(line.trimEnd());

        if (!onlyComment) {
            if (/^when\b.*=>\s*$/.test(normalized) || /^default\b.*=>\s*$/.test(normalized)) {
                indent += 1;
            } else if (/^else\b/.test(normalized)) {
                indent += 1;
            } else if (/^case\b.*\bis\s*$/.test(normalized)) {
                indent += 1;
            } else if (increasesIndentAfter(normalized)) {
                indent += 1;
            }
        }
    }

    while (out.length > 0 && out[out.length - 1] === '') out.pop();
    return out.join('\n') + '\n';
}

function activate(context) {
    const vscode = require('vscode');
    const formatProvider = vscode.languages.registerDocumentFormattingEditProvider('freehold', {
        provideDocumentFormattingEdits(document) {
            const cfg = vscode.workspace.getConfiguration('freehold.format');
            const indentSize = cfg.get('indentSize', 4);
            const fullRange = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
            return [vscode.TextEdit.replace(fullRange, formatFreehold(document.getText(), indentSize))];
        }
    });

    const command = vscode.commands.registerCommand('freehold.formatDocument', async () => {
        await vscode.commands.executeCommand('editor.action.formatDocument');
    });

    const completionProvider = vscode.languages.registerCompletionItemProvider('freehold', {
        provideCompletionItems() {
            const cfg = vscode.workspace.getConfiguration('freehold.completion');
            if (!cfg.get('enabled', true)) return [];
            return createCompletionItems(vscode);
        }
    }, '.', '<');

    context.subscriptions.push(formatProvider, completionProvider, command);
}

function deactivate() {}

module.exports = { activate, deactivate, formatFreehold, normalizeSpaces, splitLineComment, completionEntries };
