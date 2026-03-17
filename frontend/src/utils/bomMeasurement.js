export function startBomMeasurement({
  items,
  method = 'ROUGH_STOCK',
  onOpen,
  onProgress,
  onLog,
  onDone,
  onError,
  onClose,
}) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/catia/bom/calculate/ws`

  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    onOpen?.(ws)
    ws.send(JSON.stringify({ items, method }))
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.progress !== undefined) onProgress?.(data.progress, data)
    if (data.log) onLog?.(data.log, data)
    if (data.status === 'done') onDone?.(data)
    if (data.error) onError?.(data.error, data)
  }

  ws.onerror = (event) => {
    onError?.('Connection error.', event)
  }

  ws.onclose = (event) => {
    onClose?.(event)
  }

  return ws
}

export function measureBomItems({ items, method = 'ROUGH_STOCK' }) {
  return new Promise((resolve, reject) => {
    let settled = false
    const logs = []
    const ws = startBomMeasurement({
      items,
      method,
      onLog: (log) => logs.push(log),
      onDone: (data) => {
        if (settled) return
        settled = true
        resolve({
          ...data,
          logs,
        })
        try {
          ws.close()
        } catch (_) {}
      },
      onError: (error) => {
        if (settled) return
        settled = true
        reject(new Error(error))
        try {
          ws.close()
        } catch (_) {}
      },
      onClose: () => {
        if (!settled) {
          settled = true
          reject(new Error('Measurement connection closed before completion.'))
        }
      },
    })
  })
}
