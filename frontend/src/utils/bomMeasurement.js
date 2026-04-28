export function startBomMeasurement({
  items,
  projectName,
  method = 'STL',
  tempRenameDuplicateBodies = false,
  onOpen,
  onProgress,
  onLog,
  onResultRow,
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
    const payload = { items, method, projectName }
    if (tempRenameDuplicateBodies) payload.tempRenameDuplicateBodies = true
    ws.send(JSON.stringify(payload))
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.progress !== undefined) onProgress?.(data.progress, data)
    if (data.log) onLog?.(data.log, data)
    if (data.result) onResultRow?.(data.result, data)
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

export function measureBomItems({ items, projectName, method = 'STL', tempRenameDuplicateBodies = false, onAction, onLog, onResultRow }) {
  return new Promise((resolve, reject) => {
    let settled = false
    const logs = []
    
    const connect = () => {
      const ws = startBomMeasurement({
        items,
        projectName,
        method,
        tempRenameDuplicateBodies,
        onLog: (log, data) => {
           logs.push(log)
           onLog?.(log, data)
        },
        onResultRow,
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
          // Ignore error, onclose will trigger reconnect
        },
        onClose: () => {
          if (!settled) {
            onLog?.("⚠️ Connection lost. Crash detected. The Watchdog is restarting the measurement engine. Auto-resuming in 3 seconds...", {})
            setTimeout(connect, 3000)
          }
        },
      })
    }
    
    connect()
  })
}
