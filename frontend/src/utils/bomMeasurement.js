export function startBomMeasurement({
  items,
  method = 'STL',
  tempRenameDuplicateBodies = false,
  onOpen,
  onProgress,
  onLog,
  onDone,
  onError,
  onClose,
  onAction,
}) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/catia/bom/calculate/ws`

  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    onOpen?.(ws)
    const payload = { items, method }
    if (tempRenameDuplicateBodies) payload.tempRenameDuplicateBodies = true
    ws.send(JSON.stringify(payload))
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.progress !== undefined) onProgress?.(data.progress, data)
    if (data.log) onLog?.(data.log, data)
    if (data.action) {
      onAction?.(data.action, data, ws)
    }
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

export function measureBomItems({ items, method = 'STL', tempRenameDuplicateBodies = false, onAction, onLog }) {
  return new Promise((resolve, reject) => {
    let settled = false
    const logs = []
    const ws = startBomMeasurement({
      items,
      method,
      tempRenameDuplicateBodies,
      onLog: (log, data) => {
         logs.push(log)
         onLog?.(log, data)
      },
      onAction,
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
