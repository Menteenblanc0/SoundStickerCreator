export function waitEvent(sock, event, predicate, ms, emitter = sock.ev) {
    let listener
    let close
    let timer
    const dispose = () => {
        clearTimeout(timer)
        emitter.off(event, listener)
        sock.ev.off('connection.update', close)
    }
    const promise = new Promise((resolve, reject) => {
        timer = setTimeout(() => {
            dispose()
            reject(new Error('timeout'))
        }, ms)
        listener = value => {
            const found = predicate(value)
            if (found !== undefined) {
                dispose()
                resolve(found)
            }
        }
        close = update => {
            if (update.connection === 'close') {
                dispose()
                reject(new Error('closed'))
            }
        }
        emitter.on(event, listener)
        if (event !== 'connection.update') sock.ev.on('connection.update', close)
    })
    promise.catch(() => {})
    return { promise, dispose }
}

