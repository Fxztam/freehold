const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { formatFreehold, completionEntries } = require('../extension');

const input = fs.readFileSync(path.join(__dirname, '..', 'examples', 'retail_analytics_one_page_unformatted.fh'), 'utf8');
const output = formatFreehold(input, 4);

assert(output.includes('import Retail.Types exposing Customer, Basket'));
assert(output.includes('end record'));
assert(output.includes('Set.from_array(raw)'));
assert(output.includes('case count is'));
assert(output.includes('when 3 =>'));
assert(output.includes('end case'));
assert(output.includes('basket.owner.name := String.replace'));
assert(output.includes('/**'));
assert(output.endsWith('\n'));
fs.writeFileSync(path.join(__dirname, '..', 'examples', 'retail_analytics_one_page_formatted.fh'), output, 'utf8');

const completions = completionEntries();
const labels = new Set(completions.map(item => item.label));
assert(labels.has('service'));
assert(labels.has('rpc'));
assert(labels.has('proto'));
assert(labels.has('Array'));
assert(labels.has('Result'));
assert(labels.has('String.concat'));
assert(labels.has('Json.stringify'));
assert(labels.has('service rpc'));
assert(labels.has('scope block'));
assert(completions.find(item => item.label === 'record type').insertText.includes('proto ${4:1}'));
console.log('Freehold VS Code language support smoke test passed.');
