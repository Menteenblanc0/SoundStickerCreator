import protobuf from 'protobufjs/minimal.js'
import { proto, prepareWAMessageMedia } from '@whiskeysockets/baileys'

// Upstream rc14 lacks these fields. Compatibility is covered by byte-level tests.
function extend(type, name, number, child) {
    const encode = type.encode
    const decode = type.decode
    type.encode = function (message, writer) {
        const result = encode.call(this, message, writer)
        if (message[name] != null) {
            child.encode(message[name], result.uint32(number * 8 + 2).fork()).ldelim()
        }
        return result
    }
    type.decode = function (source, length, endTag) {
        const reader = source instanceof protobuf.Reader ? source : protobuf.Reader.create(source)
        const start = reader.pos
        const message = decode.call(this, reader, length, endTag)
        const end = reader.pos
        const scan = protobuf.Reader.create(reader.buf.subarray(start, end))
        while (scan.pos < scan.len) {
            const tag = scan.uint32()
            if (tag === endTag) break
            if (tag === number * 8 + 2) {
                const payload = scan.bytes()
                message[name] = child.decode(payload)
            } else {
                scan.skipType(tag & 7)
            }
        }
        return message
    }
}

extend(proto.Message.StickerMessage, 'audioMessage', 26, proto.Message.AudioMessage)
extend(proto.Message, 'audioStickerMessage', 134, proto.Message.FutureProofMessage)

export function summarize(root) {
    let node = root
    const wrappers = []
    const wrapperNames = ['audioStickerMessage', 'ephemeralMessage', 'viewOnceMessage',
        'viewOnceMessageV2', 'viewOnceMessageV2Extension', 'deviceSentMessage']
    for (let i = 0; i < 8 && node && !node.stickerMessage; i++) {
        const wrapper = wrapperNames.find(key => node[key]?.message)
        if (!wrapper) break
        wrappers.push(wrapper)
        node = node[wrapper].message
    }
    const sticker = node?.stickerMessage
    if (!sticker) return { type: wrappers[0] ?? 'other', wrappers }
    const audio = sticker.audioMessage
    return {
        type: 'stickerMessage', wrappers, audioPresent: !!audio,
        forwarded: sticker.contextInfo?.isForwarded ?? null,
        sticker: {
            mimeType: sticker.mimetype === 'image/webp' ? 'image/webp' : null,
            width: sticker.width ?? null, height: sticker.height ?? null,
            animated: sticker.isAnimated ?? null, bytes: Number(sticker.fileLength ?? 0),
            hasMediaReference: !!(sticker.directPath || sticker.url)
        },
        audio: audio ? {
            mimeType: ['audio/ogg; codecs=opus', 'audio/ogg', 'audio/mpeg', 'audio/mp4'].includes(audio.mimetype)
                ? audio.mimetype : null,
            seconds: audio.seconds ?? null, voiceNote: audio.ptt ?? null,
            waveformPresent: !!audio.waveform?.length,
            bytes: Number(audio.fileLength ?? 0), hasMediaReference: !!(audio.directPath || audio.url)
        } : null
    }
}

export async function buildMessage({ sticker, audio, metadata, upload, logger }) {
    const opts = { upload, logger, mediaUploadTimeoutMs: 45_000 }
    const result = await prepareWAMessageMedia({
        sticker, mimetype: 'image/webp', isAnimated: metadata.animated,
        width: metadata.width, height: metadata.height
    }, opts)
    const sound = await prepareWAMessageMedia({
        audio, mimetype: 'audio/ogg; codecs=opus', seconds: Math.ceil(metadata.audioSeconds),
        ptt: true
    }, opts)
    result.stickerMessage.audioMessage = sound.audioMessage
    const roundTrip = proto.Message.decode(proto.Message.encode(result).finish())
    const decoded = roundTrip.stickerMessage
    if (!decoded?.mediaKey?.length || !decoded.audioMessage?.mediaKey?.length ||
        !decoded.directPath || !decoded.audioMessage.directPath || roundTrip.audioMessage) {
        throw new Error('Falló la verificación del mensaje serializado')
    }
    return roundTrip
}
