/**
 * 一键启动本地开发服务（无需 npm install）
 *
 * 用法：
 *   node dev.js
 *
 * 同时启动：
 * - 后端 API：uvicorn（端口 8002，因 8000/8001 被 Docker Desktop 占用）
 * - Celery Worker：异步任务队列（AI 回测等）
 * - Celery Beat：定时任务调度
 * - 前端：vite（端口 3000）
 *
 * 按 Ctrl+C 停止所有服务。
 *
 * 环境要求：
 * - Redis 运行中（默认 localhost:6379，可通过 REDIS_URL 环境变量覆盖）
 * - Python 虚拟环境已安装依赖
 */

const { spawn } = require('child_process');
const path = require('path');

const ROOT = __dirname;
const BACKEND_DIR = path.join(ROOT, 'backend');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const VENV_DIR = path.join(BACKEND_DIR, '.venv');
const BACKEND_PORT = '8002';

// 子进程列表，用于优雅退出
const children = [];

/**
 * 安全启动子进程，捕获启动错误。
 */
function safeSpawn(name, command, args, opts = {}) {
  console.log(`  ⏳ 正在启动 ${name}...`);
  const child = spawn(command, args, {
    stdio: 'inherit',
    ...opts,
  });
  children.push(child);

  child.on('error', (err) => {
    console.error(`\n❌ ${name} 启动失败: ${err.message}`);
  });

  child.on('exit', (code) => {
    if (code !== null && code !== 0) {
      console.error(`\n⚠️  ${name} 异常退出 (code: ${code})`);
    }
  });

  return child;
}

// 后端 API
safeSpawn('后端 API', path.join(VENV_DIR, 'bin', 'uvicorn'), [
  'app.main:app', '--reload', '--port', BACKEND_PORT,
], {
  cwd: BACKEND_DIR,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
});

// Celery Worker（异步任务队列，监听 default 和 celery 队列）
safeSpawn('Celery Worker', path.join(VENV_DIR, 'bin', 'celery'), [
  '-A', 'app.tasks', 'worker',
  '--loglevel=info',
  '--concurrency=2',
  '--queues=default,celery',
], {
  cwd: BACKEND_DIR,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
});

// Celery Beat（定时任务调度，如清理 stale pending 回测）
safeSpawn('Celery Beat', path.join(VENV_DIR, 'bin', 'celery'), [
  '-A', 'app.tasks', 'beat',
  '--loglevel=info',
], {
  cwd: BACKEND_DIR,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
});

// 前端（覆盖 proxy target 指向后端端口）
safeSpawn('前端', 'npx', ['vite', '--port', '3000'], {
  cwd: FRONTEND_DIR,
  env: {
    ...process.env,
    VITE_PROXY_TARGET: `http://localhost:${BACKEND_PORT}`,
    VITE_WS_URL: `ws://localhost:${BACKEND_PORT}`,
  },
});

console.log(`\n🚀 服务启动中...`);
console.log(`   后端: http://localhost:${BACKEND_PORT}`);
console.log(`   前端: http://localhost:3000`);
console.log(`   Celery Worker: 正在监听任务队列`);
console.log(`   Celery Beat: 正在调度定时任务`);
console.log(`   按 Ctrl+C 停止\n`);

// 优雅退出
process.on('SIGINT', () => {
  console.log('\n⏹ 正在停止服务...');
  children.forEach(child => child.kill('SIGTERM'));
  setTimeout(() => process.exit(0), 2000);
});

process.on('SIGTERM', () => {
  children.forEach(child => child.kill('SIGTERM'));
  process.exit(0);
});