// Run TI's installed CLI launcher as CommonJS without changing its installation.
// Needed here because D:/Apps/package.json declares type=module, while TI's
// app-launcher.js uses CommonJS. Pass the normal ccs-server-cli arguments.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const eclipse = 'D:/Apps/ccs/eclipse';
const plugins = fs.readdirSync(path.join(eclipse, 'plugins'))
  .filter(name => name.startsWith('com.ti.ccs.apps_')).sort();
if (!plugins.length) throw new Error('CCS CLI plugin was not found.');
const original = path.join(eclipse, 'plugins', plugins.at(-1), 'scripts', 'app-launcher.js');
process.argv[1] = original;
const launcher = new Module(original, module);
launcher.filename = original;
launcher.paths = Module._nodeModulePaths(path.dirname(original));
launcher._compile(fs.readFileSync(original, 'utf8'), original);
