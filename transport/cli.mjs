import { readFile, stat } from 'node:fs/promises'
import { parseArgs } from 'node:util'
import qr from 'qrcode-terminal'
import QRCode from 'qrcode-terminal/vendor/QRCode/index.js'
import {
    makeWASocket, DisconnectReason, initAuthCreds, generateMessageIDV2,
    jidNormalizedUser
} from '@whiskeysockets/baileys'
import { buildMessage, summarize } from './protocol.mjs'
import { measure } from './diagnostic.mjs'
import { waitEvent } from './events.mjs'

const silent = Object.fromEntries(['trace', 'debug', 'info', 'warn', 'error', 'fatal']
    .map(level => [level, () => {}]))
silent.child = () => silent
silent.level = 'silent'

function memoryAuth() {
    const data = new Map()
    return {
        creds: initAuthCreds(),
        keys: {
            async get(type, ids) {
                const entries = data.get(type)
                return Object.fromEntries(ids.filter(id => entries?.has(id)).map(id => [id, entries.get(id)]))
            },
            async set(changes) {
                for (const [type, values] of Object.entries(changes)) {
                    if (!data.has(type)) data.set(type, new Map())
                    const entries = data.get(type)
                    for (const [id, value] of Object.entries(values)) {
                        if (value == null) entries.delete(id)
                        else entries.set(id, value)
                    }
                }
            }
        }
    }
}

async function connect(auth, gui) {
    for (let attempt = 0; attempt < 2; attempt++) {
        const sock = makeWASocket({
            auth, logger: silent, syncFullHistory: false, fireInitQueries: false,
            shouldSyncHistoryMessage: () => false, markOnlineOnConnect: false,
            emitOwnEvents: false, enableRecentMessageCache: false,
            getMessage: async () => undefined,
            connectTimeoutMs: 25_000, defaultQueryTimeoutMs: 30_000
        })
        const credentials = update => Object.assign(auth.creds, update)
        const showQR = update => {
            if (update.qr) {
                console.log('Escanea con la cuenta de pruebas en Dispositivos vinculados.')
                if (gui) {
                    const matrix = new QRCode(-1, qr.error)
                    matrix.addData(update.qr)
                    matrix.make()
                    console.log('QR:' + JSON.stringify(matrix.modules.map(row =>
                        row.map(dark => dark ? '1' : '0').join(''))))
                } else {
                    qr.generate(update.qr, { small: true }, code =>
                        console.log(process.stdout.isTTY ? '\x1b[97;40m' + code + '\x1b[0m' : code))
                }
            }
        }
        sock.ev.on('creds.update', credentials)
        sock.ev.on('connection.update', showQR)
        try {
            const result = await waitEvent(sock, 'connection.update', update =>
                ['open', 'close'].includes(update.connection) ? update : undefined, 150_000).promise
            if (result.connection === 'open') return sock
            if (result.lastDisconnect?.error?.output?.statusCode !== DisconnectReason.restartRequired) {
                throw new Error('connection closed')
            }
        } catch (error) {
            sock.end(undefined)
            throw error
        } finally {
            sock.ev.off('connection.update', showQR)
        }
    }
    throw new Error('could not reconnect')
}

let phase = 'validación de parámetros'
let sock
try {
    const { values: args, positionals } = parseArgs({
        args: process.argv.slice(2), allowPositionals: true,
        options: {
            sticker: { type: 'string' }, audio: { type: 'string' }, metadata: { type: 'string' },
            to: { type: 'string' }, self: { type: 'boolean' },
            'test-account': { type: 'boolean' }, measure: { type: 'boolean' }, gui: { type: 'boolean' }
        }
    })
    const [action] = positionals
    if (positionals.length !== 1 || !['send', 'receive'].includes(action) || !args['test-account']) {
        throw new Error('usage')
    }
    let material
    if (action === 'send') {
        if (!args.sticker || !args.audio || !args.metadata ||
            (!!args.self === !!args.to) || (args.to && !/^\+?[1-9][0-9]{6,14}$/.test(args.to))) {
            throw new Error('invalid destination or inputs')
        }
        for (const [path, limit] of [[args.metadata, 256 * 1024], [args.sticker, 8 * 1024 ** 2],
            [args.audio, 2 * 1024 ** 2]]) {
            const info = await stat(path)
            if (!info.isFile() || info.size < 1 || info.size > limit) throw new Error('invalid file')
        }
        const metadata = JSON.parse(await readFile(args.metadata, 'utf8'))
        const sticker = await readFile(args.sticker)
        const audio = await readFile(args.audio)
        const webp = sticker.length >= 12 && sticker.toString('ascii', 0, 4) === 'RIFF'
            && sticker.toString('ascii', 8, 12) === 'WEBP'
        if (!webp || sticker.length > 8 * 1024 ** 2 || audio.length > 2 * 1024 ** 2 ||
            audio.toString('ascii', 0, 4) !== 'OggS' ||
            !audio.subarray(0, 256).includes(Buffer.from('OpusHead')) ||
            ![metadata.width, metadata.height].every(value => Number.isInteger(value) && value > 0 && value <= 1024) ||
            typeof metadata.animated !== 'boolean' || !Number.isFinite(metadata.audioSeconds) ||
            metadata.audioSeconds <= 0 || metadata.audioSeconds > 30.02) {
            throw new Error('invalid media')
        }
        material = { sticker, audio, metadata }
    }
    phase = 'vinculación'
    sock = await connect(memoryAuth(), args.gui)
    console.log('Conectado.')
    if (action === 'receive') {
        phase = 'espera de sticker entrante (120 segundos)'
        console.log('Reenvía un sticker sonoro desde otra cuenta de pruebas.')
        const incoming = waitEvent(sock, 'messages.upsert', batch => {
            if (batch.type !== 'notify') return
            for (const entry of batch.messages) {
                if (entry.key.fromMe || !entry.message) continue
                const report = summarize(entry.message)
                if (report.type === 'stickerMessage' || report.wrappers.includes('audioStickerMessage')) return { report, message: entry.message }
            }
        }, 120_000)
        const { report, message } = await incoming.promise
        if (args.measure) report.measured = await measure(message, report.wrappers)
        console.log(JSON.stringify(report, null, 2))
    } else {
        phase = 'carga de medios y serialización'
        const destination = args.self ? jidNormalizedUser(sock.user.id) : args.to.replace(/^\+/, '') + '@s.whatsapp.net'
        const message = await buildMessage({ ...material, upload: sock.waUploadToServer, logger: silent })
        console.log(JSON.stringify(summarize(message), null, 2))
        phase = 'envío o confirmación del servidor'
        const messageId = generateMessageIDV2(sock.user.id)
        const ack = waitEvent(sock, 'CB:ack,class:message', node =>
            node?.attrs?.id === messageId ? !node.attrs.error : undefined, 30_000, sock.ws)
        try {
            await sock.relayMessage(destination, message, { messageId })
            console.log('Mensaje transmitido. Esperando confirmación del servidor.')
            const status = await ack.promise
            if (!status) throw new Error('ack rejected')
            console.log('Servidor confirmó el mensaje. Comprueba el sonido en el dispositivo receptor.')
        } finally {
            ack.dispose()
        }
    }
} catch {
    console.error('Error durante la fase de ' + phase + '.')
    process.exitCode = 1
} finally {
    if (sock) {
        // The credential store lives in memory. Revoke the linked device on completion.
        let timeout
        try {
            await Promise.race([sock.logout(), new Promise((_, reject) => {
                timeout = setTimeout(reject, 10_000)
            })])
        } catch {
            console.error('Revoca esta vinculación en Dispositivos vinculados si todavía aparece.')
        } finally {
            clearTimeout(timeout)
            sock.end(undefined)
        }
    }
}
