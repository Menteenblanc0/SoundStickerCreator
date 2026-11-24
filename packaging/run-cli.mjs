import { spawnSync } from 'node:child_process'

const python = process.env.SOUND_STICKER_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
const result = spawnSync(python, ['app.py', ...process.argv.slice(2)], { stdio: 'inherit' })
if (result.error) console.error('No se pudo iniciar Python. Configura SOUND_STICKER_PYTHON.')
process.exitCode = result.status ?? 1
