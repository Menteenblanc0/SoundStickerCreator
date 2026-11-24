import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { proto } from '@whiskeysockets/baileys'
import { buildMessage, summarize } from './protocol.mjs'

test('nested audio uses sticker field 26 with length-delimited wire type', () => {
    const bytes = proto.Message.encode({
        stickerMessage: { audioMessage: { seconds: 2 } }
    }).finish()
    assert.deepEqual([...bytes], [210, 1, 5, 210, 1, 2, 40, 2])
    assert.equal(proto.Message.decode(bytes).stickerMessage.audioMessage.seconds, 2)
})

test('field 134 decodes as a FutureProofMessage without implying server behavior', () => {
    const wrapped = {
        audioStickerMessage: { message: { stickerMessage: { audioMessage: { seconds: 7 } } } }
    }
    const bytes = proto.Message.encode(wrapped).finish()
    assert.deepEqual([...bytes.slice(0, 2)], [178, 8])
    const report = summarize(proto.Message.decode(bytes))
    assert.deepEqual(report.wrappers, ['audioStickerMessage'])
    assert.equal(report.audio.seconds, 7)
})

test('upload callback gets two different encrypted assets and produces one message', async () => {
    const uploads = new Map()
    const message = await buildMessage({
        sticker: Buffer.from('sticker fixture'),
        audio: Buffer.from('audio fixture'),
        metadata: { animated: true, width: 256, height: 256, audioSeconds: 1.5 },
        upload: async (file, { mediaType }) => {
            uploads.set(mediaType, await readFile(file))
            return { directPath: '/mms/' + mediaType, mediaUrl: 'https://mmg.whatsapp.net/mms/' + mediaType }
        }
    })
    assert.deepEqual([...uploads.keys()], ['sticker', 'audio'])
    assert.ok(!uploads.get('sticker').includes('sticker fixture'))
    assert.ok(!uploads.get('audio').includes('audio fixture'))
    const report = summarize(message)
    assert.equal(report.audio.seconds, 2)
    assert.equal(report.sticker.width, 256)
    assert.equal(message.audioMessage, null)
    assert.doesNotMatch(JSON.stringify(report), /mmg|directPath|mediaKey/)
})

test('a failed upload prevents construction of a relayable message', async () => {
    await assert.rejects(buildMessage({
        sticker: Buffer.from('webp'), audio: Buffer.from('opus'),
        metadata: { animated: false, width: 256, height: 256, audioSeconds: 1 },
        upload: async () => { throw new Error('mock failure') }
    }), /mock failure/)
})

test('connection closure and timeout remove pending listeners', async () => {
    const { EventEmitter } = await import('node:events')
    const { waitEvent } = await import('./events.mjs')
    const sock = { ev: new EventEmitter(), ws: new EventEmitter() }
    const ack = waitEvent(sock, 'ack', value => value, 500, sock.ws)
    sock.ev.emit('connection.update', { connection: 'close' })
    await assert.rejects(ack.promise, /closed/)
    assert.equal(sock.ev.listenerCount('connection.update'), 0)
    assert.equal(sock.ws.listenerCount('ack'), 0)
    const delayed = waitEvent(sock, 'ack', value => value, 10, sock.ws)
    await assert.rejects(delayed.promise, /timeout/)
    assert.equal(sock.ws.listenerCount('ack'), 0)
})

test('a foreign ack is ignored and a matching negative ack is distinguishable', async () => {
    const { EventEmitter } = await import('node:events')
    const { waitEvent } = await import('./events.mjs')
    const sock = { ev: new EventEmitter(), ws: new EventEmitter() }
    const ack = waitEvent(sock, 'ack', node => node.id === 'target' ? !node.error : undefined, 500, sock.ws)
    sock.ws.emit('ack', { id: 'other' })
    sock.ws.emit('ack', { id: 'target', error: 'example' })
    assert.strictEqual(await ack.promise, false)
})

test('diagnostics read dimension bytes without carrying incoming identifiers', async () => {
    const { imageHeader } = await import('./diagnostic.mjs')
    const head = Buffer.from('524946461600000057454250565038580a00000002000000ff00007f0000', 'hex')
    assert.deepEqual(imageHeader(head), { width: 256, height: 128, animated: true })
    assert.throws(() => imageHeader(head.subarray(0, 25)), /invalid WebP/)
})
