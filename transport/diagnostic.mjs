import { createHash } from 'node:crypto'
import { downloadContentFromMessage } from '@whiskeysockets/baileys'
import { parseBuffer } from 'music-metadata'

async function checkedMedia(descriptor, type, maxBytes) {
    const { directPath, mediaKey, fileSha256, fileLength } = descriptor
    const size = Number(fileLength)
    if (!/^\/[\w-]+\/[\x21-\x7e]+$/.test(directPath ?? '') ||
        !mediaKey?.length || fileSha256?.length !== 32 ||
        !Number.isSafeInteger(size) || size < 1 || size > maxBytes) {
        throw new Error('unsupported media descriptor')
    }
    const stream = await downloadContentFromMessage({ directPath, mediaKey }, type, {
        host: 'mmg.whatsapp.net', options: { redirect: 'error', signal: AbortSignal.timeout(20_000) }
    })
    const chunks = []
    let bytes = 0
    for await (const chunk of stream) {
        bytes += chunk.length
        if (bytes > maxBytes) throw new Error('media exceeds limit')
        chunks.push(chunk)
    }
    const data = Buffer.concat(chunks)
    if (bytes !== size || !createHash('sha256').update(data).digest().equals(fileSha256)) {
        throw new Error('media integrity check failed')
    }
    return data
}

export function imageHeader(data) {
    if (data.length < 20 || data.toString('ascii', 0, 4) !== 'RIFF' ||
        data.toString('ascii', 8, 12) !== 'WEBP' || data.readUInt32LE(4) + 8 > data.length) {
        throw new Error('invalid WebP')
    }
    const kind = data.toString('ascii', 12, 16)
    const length = data.readUInt32LE(16)
    if (length + 20 > data.length) throw new Error('truncated WebP')
    if (kind === 'VP8X' && length === 10) {
        return { width: 1 + data.readUIntLE(24, 3), height: 1 + data.readUIntLE(27, 3),
            animated: !!(data[20] & 2) }
    }
    if (kind === 'VP8 ' && length >= 10 && data.readUIntLE(23, 3) === 0x2a019d) {
        return { width: data.readUInt16LE(26) & 16383, height: data.readUInt16LE(28) & 16383, animated: false }
    }
    if (kind === 'VP8L' && length >= 5 && data[20] === 47) {
        const bits = data.readUInt32LE(21)
        return { width: 1 + (bits & 16383), height: 1 + ((bits >>> 14) & 16383), animated: false }
    }
    throw new Error('unsupported WebP')
}

export async function measure(root, wrappers) {
    const sticker = wrappers.reduce((message, key) => message?.[key]?.message, root)?.stickerMessage
    if (!sticker) return {}
    const outcomes = await Promise.allSettled([
        checkedMedia(sticker, 'sticker', 8 * 1024 ** 2).then(imageHeader),
        (async () => {
            if (!sticker.audioMessage) return null
            const data = await checkedMedia(sticker.audioMessage, 'audio', 2 * 1024 ** 2)
            const { format } = await parseBuffer(data, undefined, { duration: true, skipCovers: true })
            const codec = ['Opus', 'Vorbis I', 'MPEG 1 Layer 3', 'FLAC', 'AAC', 'PCM'].includes(format.codec)
                ? format.codec : null
            return { codec, seconds: format.duration ?? null, sampleRate: format.sampleRate ?? null }
        })()
    ])
    const value = result => result.status === 'fulfilled' ? result.value : { error: 'media-unavailable-or-invalid' }
    return { sticker: value(outcomes[0]), audio: value(outcomes[1]) }
}
