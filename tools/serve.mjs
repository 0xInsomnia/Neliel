import { spawn } from 'node:child_process';
const args = process.argv.slice(2);
const port = args.includes('--port') ? args[args.indexOf('--port') + 1] : '8080';
const child = spawn('python3', ['-m', 'http.server', port, '--bind', '0.0.0.0'], { stdio: 'inherit' });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('exit', code => process.exit(code ?? 0));
