import { useState, useEffect, useRef, useMemo } from 'react'
import { flushSync } from 'react-dom'
import { startBomMeasurement } from '../utils/bomMeasurement'
import { getNameSuggestions } from '../utils/bomNaming'

const DEFAULT_METHOD = 'STL'

function mergeClassificationIntoResults(classifiedRows, resultRows) {
  const map = new Map()
  for (const r of resultRows || []) {
    const keys = [
      r.sourceRowId,
      `${r.id}|${r.instanceName || ''}`,
      `${r.partNumber || r.id}|${r.instanceName || ''}`,
    ].filter(Boolean)
    for (const k of keys) map.set(k, r)
  }
  
  return (classifiedRows || []).filter(c => c.selected !== false).map((c) => {
    const k =
      c.sourceRowId ||
      `${c.partNumber || c.id}|${c.instanceName || ''}` ||
      `${c.id}|${c.instanceName || ''}`
    const r =
      map.get(c.sourceRowId) ||
      map.get(`${c.id}|${c.instanceName || ''}`) ||
      map.get(`${c.partNumber || c.id}|${c.instanceName || ''}`) ||
      map.get(k)

    if (!r) return c

    return {
      ...c,
      ...r,
      isStd: c.isStd,
      sheetCategory: c.sheetCategory,
      exportBucket: c.sheetCategory || c.exportBucket || r.exportBucket,
      material: c.material != null && c.material !== '' ? c.material : r.material,
      manufacturer: c.manufacturer != null && c.manufacturer !== '' ? c.manufacturer : r.manufacturer,
      description: c.description || r.description,
      measurementBodyName: r.measurementBodyName || c.measurementBodyName,
      bodyNameOptions: c.bodyNameOptions || r.bodyNameOptions,
    }
  })
}

function newManualRowId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return `manual-${crypto.randomUUID()}`
  return `manual-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function normalizeRows(items) {
  return (items || []).map((item) => {
    const incomingCategory = item.sheetCategory || ''
    const isStd = item.isStd || incomingCategory.startsWith('STD')
    const sheetCategory = isStd ? 'STD' : (incomingCategory && ['Steel', 'MS', 'Casting'].includes(incomingCategory) ? incomingCategory : 'Steel')
    const isManualRow = !!item.isManualRow
    const inst = (item.instanceName || '').trim()
    return {
      ...item,
      isManualRow,
      isClonedRow: !!item.isClonedRow,
      sourceRowId: item.sourceRowId || item.id,
      selected: item.selected !== false,
      isStd,
      sheetCategory,
      manufacturer: item.manufacturer || (isStd ? 'MISUMI' : ''),
      description: item.description || getNameSuggestions(item)[0] || item.instanceName || item.name,
      material: item.material || '',
      measurementBodyName: item.measurementBodyName || '',
      bodyNameOptions: Array.isArray(item.bodyNameOptions) ? item.bodyNameOptions : [],
      _bodyFetchPending: false,
      measureBodyColumnHint: item.measureBodyColumnHint || '',
      partNumber: isManualRow ? (item.partNumber || '').trim() : item.partNumber,
      instances: Array.isArray(item.instances) && item.instances.length
        ? item.instances
        : inst
          ? [inst]
          : item.instances || [],
    }
  })
}

export default function BOMSelectionList({ items: initialItems, projectName, bomOptions = {}, onAction, onUpdate, onCalculationComplete, onPartialExport }) {
  const [items, setItems] = useState(() => normalizeRows(initialItems))
  const [calculating, setCalculating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [logs, setLogs] = useState([])
  const [pendingAction, setPendingAction] = useState(null)
  const [selectorError, setSelectorError] = useState('')
  const [bodyListError, setBodyListError] = useState('')
  const [measureMethod, setMeasureMethod] = useState(DEFAULT_METHOD)
  const [dragRowIndex, setDragRowIndex] = useState(null)
  const [dropTargetIndex, setDropTargetIndex] = useState(null)
  const wsRef = useRef(null)
  const logEndRef = useRef(null)
  const cancelledRef = useRef(false)
  const itemsRef = useRef(items)

  const lastSyncedItemsRef = useRef(null)

  useEffect(() => {
    const nextNormalized = normalizeRows(initialItems)
    const nextJson = JSON.stringify(nextNormalized)
    if (nextJson !== lastSyncedItemsRef.current) {
      setItems(nextNormalized)
      lastSyncedItemsRef.current = nextJson
    }
  }, [initialItems])

  useEffect(() => {
    itemsRef.current = items
    const nextJson = JSON.stringify(items)
    if (onUpdate && nextJson !== lastSyncedItemsRef.current) {
      lastSyncedItemsRef.current = nextJson
      onUpdate(items);
    }
  }, [items, onUpdate])

  const bodyFetchKey = useMemo(() => {
    const flag = bomOptions?.tempRenameDuplicateBodies ? '1' : '0'
    const rows = items
      .filter((i) => i.selected)
      .map((i) => `${i.id}|${i.instanceName}`)
      .sort()
      .join(';')
    return rows ? `${flag}|${rows}` : ''
  }, [items, bomOptions?.tempRenameDuplicateBodies])

  useEffect(() => {
    if (!bodyFetchKey) {
      setBodyListError('')
      fetch('/api/catia/bom/body-disambiguation/reset', { method: 'POST' }).catch(() => {})
      setItems((prev) =>
        prev.map((r) => ({ ...r, _bodyFetchPending: false, measureBodyColumnHint: '' })),
      )
      return undefined
    }
    setItems((prev) =>
      prev.map((row) =>
        row.selected ? { ...row, _bodyFetchPending: true, measureBodyColumnHint: '' } : row,
      ),
    )
    const payloadItems = itemsRef.current
      .filter((i) => i.selected)
      .map((i) => ({
        id: i.id,
        partNumber: i.partNumber,
        instanceName: i.instanceName,
        sourceRowId: i.sourceRowId,
        instances: i.instances,
        sourceDocPath: i.sourceDocPath,
        name: i.name,
        isManualRow: !!i.isManualRow,
      }))
    const ac = new AbortController()
    const t = setTimeout(() => {
      fetch('/api/catia/bom/part-bodies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: payloadItems,
          tempRenameDuplicateBodies: !!bomOptions?.tempRenameDuplicateBodies,
        }),
        signal: ac.signal,
      })
        .then((r) => r.json())
        .then((data) => {
          if (!data || data.error) {
            setBodyListError(data?.error || 'Could not load body lists from CATIA')
            setItems((prev) =>
              prev.map((row) =>
                row.selected
                  ? {
                      ...row,
                      _bodyFetchPending: false,
                      bodyNameOptions: [],
                      measureBodyColumnHint: data?.error || 'CATIA error',
                    }
                  : row,
              ),
            )
            return
          }
          setBodyListError('')
          const map = new Map()
          for (const res of data.results || []) {
            const sid = res.sourceRowId || `${res.id}|${res.instanceName || ''}`
            map.set(sid, res)
            map.set(`${res.id}|${res.instanceName || ''}`, res)
            if (res.partNumber)
              map.set(`${res.partNumber}|${res.instanceName || ''}`, res)
          }
          const hintFor = (e) =>
            e === 'unresolved'
              ? 'Not found — open the CATProduct or correct source path'
              : e === 'no_bodies'
                ? 'Part has no bodies'
                : e || ''
          setItems((prev) =>
            prev.map((row) => {
              if (!row.selected) {
                return { ...row, _bodyFetchPending: false }
              }
              const inst = row.instanceName || ''
              const r =
                map.get(row.sourceRowId) ||
                map.get(`${row.id}|${inst}`) ||
                map.get(`${row.partNumber}|${inst}`)
              if (!r) {
                return {
                  ...row,
                  bodyNameOptions: [],
                  _bodyFetchPending: false,
                  measureBodyColumnHint: 'No match — refresh BOM list',
                }
              }
              const opts = Array.isArray(r.bodies) ? r.bodies : []
              let mb = row.measurementBodyName || ''
              
              if (opts.length === 1) {
                mb = opts[0]
              } else if (opts.length > 1 && mb) {
                const mbNorm = mb.trim().toUpperCase()
                const canonicalMatch = opts.find(o => o.trim().toUpperCase() === mbNorm)
                if (canonicalMatch) {
                  mb = canonicalMatch
                }
              }
              
              const hint = opts.length === 0 && r.error ? hintFor(r.error) : ''
              return {
                ...row,
                bodyNameOptions: opts,
                measurementBodyName: mb,
                _bodyFetchPending: false,
                measureBodyColumnHint: hint,
              }
            }),
          )
        })
        .catch((e) => {
          if (e.name === 'AbortError') return
          setBodyListError('Body list request failed')
          setItems((prev) =>
            prev.map((row) =>
              row.selected
                ? {
                    ...row,
                    _bodyFetchPending: false,
                    bodyNameOptions: [],
                    measureBodyColumnHint: 'Request failed',
                  }
                : row,
            ),
          )
        })
    }, 450)
    return () => {
      clearTimeout(t)
      ac.abort()
    }
  }, [bodyFetchKey])

  useEffect(() => {
    if (calculating && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, calculating])

  const updateItem = (id, updater) => {
    setItems((prev) => prev.map((item) => (item.id === id ? updater(item) : item)))
  }

  const moveRow = (fromIndex, toIndex) => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return
    setSelectorError('')
    setItems((prev) => {
      if (fromIndex >= prev.length || toIndex >= prev.length) return prev
      const next = [...prev]
      const [row] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, row)
      return next
    })
  }

  const toggleItem = (id) => {
    setSelectorError('')
    updateItem(id, (item) => ({ ...item, selected: !item.selected }))
  }

  const selectAll = (selected) => {
    setSelectorError('')
    setItems((prev) => prev.map((item) => ({ ...item, selected })))
  }

  const updateSheetCategory = (id, value) => {
    setSelectorError('')
    updateItem(id, (item) => ({
      ...item,
      sheetCategory: value,
      isStd: value === 'STD',
      manufacturer: value === 'STD' ? (item.manufacturer || 'MISUMI') : item.manufacturer,
    }))
  }

  const updateMeasurementBody = (id, value) => {
    setSelectorError('')
    updateItem(id, (item) => ({ ...item, measurementBodyName: value }))
  }

  const addManualRow = () => {
    setSelectorError('')
    const sid = newManualRowId()
    setItems((prev) => [
      ...prev,
      normalizeRows([
        {
          isManualRow: true,
          id: sid,
          sourceRowId: sid,
          partNumber: '',
          instanceName: '',
          name: '',
          description: '',
          qty: 1,
          selected: true,
          isStd: false,
          sheetCategory: 'Steel',
          material: '',
          measurementBodyName: '',
          bodyNameOptions: [],
          instances: [],
        },
      ])[0],
    ])
  }

  const removeRow = (id) => {
    setSelectorError('')
    setItems((prev) => prev.filter((row) => row.id !== id))
  }

  const splitRow = (item, index) => {
    const qtyStr = window.prompt(`How many total BOM items exist under part "${item.instanceName || item.name || 'this item'}"?`, "2")
    if (!qtyStr) return
    const count = parseInt(qtyStr, 10)
    if (isNaN(count) || count <= 1) return

    setItems(prev => {
      const next = [...prev]
      const clones = []
      for (let i = 1; i < count; i++) {
        const sid = newManualRowId()
        clones.push(normalizeRows([{
          ...item,
          id: sid,
          isClonedRow: true,
          sourceRowId: sid,
          measurementBodyName: '',
          qty: 1,
        }])[0])
      }
      next.splice(index + 1, 0, ...clones)
      return next
    })
  }

  const validateBeforeMeasurement = (selectedItems) => {
    const manualNoInstance = selectedItems.filter((item) => item.isManualRow && !`${item.instanceName || ''}`.trim())
    if (manualNoInstance.length) return 'Manual row(s): enter the CATIA instance name before measurement.'
    const manualNoBody = selectedItems.filter(item => item.isManualRow && !item.isStd && !`${item.measurementBodyName || ''}`.trim() && (item.bodyNameOptions?.length || 0) === 0)
    if (manualNoBody.length) return 'Manual row(s): enter the measure body name exactly as in CATIA.'
    return ''
  }

  const startCalculation = () => {
    const selectedItems = items.filter((item) => item.selected)
    if (selectedItems.length === 0) return

    const validationMessage = validateBeforeMeasurement(selectedItems)
    if (validationMessage) {
      setSelectorError(validationMessage)
      return
    }

    const ambiguousBody = selectedItems.filter(it => !it.isStd && (it.bodyNameOptions?.length || 0) > 1 && !`${it.measurementBodyName || ''}`.trim())
    if (ambiguousBody.length) {
      setSelectorError(`Choose a measure body for ${ambiguousBody.length} part(s) with multiple bodies.`)
      return
    }

    const toMeasure = selectedItems.filter(it => !it.isStd && (!it.stock_size || it.stock_size === 'Measuring...' || it.stock_size === 'Unknown' || it.stock_size.includes('Error') || it.stock_size.includes('Not Measurable')))
    const skippedCount = selectedItems.length - toMeasure.length

    setCalculating(true)
    setProgress(0)
    setLogs([
      'Connecting to measure engine...',
      ...(skippedCount > 0 ? [`Skipping ${skippedCount} already measured item(s).`] : [])
    ])
    setSelectorError('')
    setPendingAction(null)
    cancelledRef.current = false

    if (toMeasure.length === 0) {
      setLogs(prev => [...prev, 'All selected items are already measured.'])
      setCalculating(false)
      return
    }

    const ws = startBomMeasurement({
      items: toMeasure,
      projectName,
      method: measureMethod,
      tempRenameDuplicateBodies: !!bomOptions?.tempRenameDuplicateBodies,
      onAction: (action, data, ws) => {
        setPendingAction({ type: action, data, ws });
        onAction?.(action, data, ws);
      },
      onOpen: () => {
        if (cancelledRef.current) return
        flushSync(() => {
          setLogs((prev) => [
            ...prev,
            `Starting measurement (${measureMethod === 'STL' ? 'STL' : 'Rough Stock'})...`,
          ])
        })
      },
      onProgress: (nextProgress) => {
        if (!cancelledRef.current) flushSync(() => setProgress(nextProgress))
      },
      onLog: (log) => {
        if (!cancelledRef.current) flushSync(() => setLogs((prev) => [...prev, log]))
      },
      onResultRow: (row) => {
        if (cancelledRef.current) return;
        setItems((prev) => prev.map(it => {
          const pMatch = it.partNumber === row.partNumber || it.id === row.id;
          const iMatch = it.instanceName === row.instanceName;
          if (pMatch && iMatch) {
            return {
              ...it,
              stock_size: row.stock_size,
              rawDims: row.rawDims,
              method_used: row.method_used,
              measurementBodyName: row.measurementBodyName || it.measurementBodyName
            };
          }
          return it;
        }));
      },
      onDone: (data) => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, `Done! Finalizing results...`])
        setTimeout(() => {
          const classified = itemsRef.current || []
          const merged = mergeClassificationIntoResults(classified, data.results || [])
          onCalculationComplete?.({
            results: merged,
            retryCandidates: data.retryCandidates || [],
          })
        }, 1000)
      },
      onError: (error) => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, `Error: ${error}`])
        setCalculating(false)
      },
      onClose: () => {},
    })
    wsRef.current = ws
  }

  const cancelCalculation = (e) => {
    e?.preventDefault?.()
    cancelledRef.current = true
    if (wsRef.current) {
      try { wsRef.current.close() } catch (_) {}
      wsRef.current = null
    }
    setCalculating(false)
    setProgress(0)
    setLogs((prev) => [...prev, 'Cancelled by user.'])
  }

  const handleActionConfirm = (command, extra = {}) => {
    if (!pendingAction?.ws) return;
    pendingAction.ws.send(JSON.stringify({ command, ...extra }));
    setLogs(prev => [...prev, `✅ Confirmed: ${command} ${extra.bodyName || ''}`]);
    setPendingAction(null);
  }

  const handlePartialExport = () => {
    const measuredItems = items.filter(it => it.stock_size && it.stock_size !== 'Measuring...' && !it.stock_size.includes('Error') && !it.stock_size.includes('Not Measurable'))
    onPartialExport?.(measuredItems)
  }

  if (calculating) {
    return (
      <div className="mt-4 p-6 zen-card border border-zen-border space-y-6 animate-in fade-in duration-500">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="zen-label text-zen-primary">Measurement in Progress</span>
            <span className="text-[10px] text-zen-text-muted mt-1 truncate max-w-[300px] font-mono">{logs[logs.length - 1]}</span>
          </div>
          <div className="flex items-center gap-3">
             <span className="text-xl font-bold text-zen-primary">{progress}%</span>
             <div className="flex items-center gap-2">
                <button type="button" onClick={handlePartialExport} className="text-[10px] font-bold px-4 py-2 rounded-full bg-zen-success/10 text-zen-success border border-zen-success/20 hover:bg-zen-success/20 transition-all">Partial Export</button>
                <button type="button" onClick={cancelCalculation} className="text-[10px] font-bold px-4 py-2 rounded-full bg-zen-error/10 text-zen-error border border-zen-error/20 hover:bg-zen-error/20 transition-all">Cancel</button>
             </div>
          </div>
        </div>

        <div className="w-full h-1.5 bg-zen-surface-alt rounded-full overflow-hidden border border-zen-border/50">
          <div className="h-full bg-zen-primary transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
        </div>

        {pendingAction && (
          <div className="p-5 rounded-3xl bg-zen-warning/5 border border-zen-warning/20 shadow-sm animate-pulse">
            <p className="text-xs font-bold text-zen-warning mb-2 flex items-center gap-2 uppercase tracking-widest">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
              Manual Intervention
            </p>
            <p className="text-[11px] text-zen-text-main mb-4 leading-relaxed">{pendingAction.data?.log || 'Please interact with CATIA as requested.'}</p>
            
            <div className="flex flex-wrap gap-2">
              {pendingAction.type === 'REQUIRE_AXIS_SELECTION' && (
                <button onClick={() => handleActionConfirm('AXIS_CONFIRMED')} className="zen-pill px-6 py-2.5 text-[10px]">
                  Confirm Axis Selected
                </button>
              )}
              {pendingAction.type === 'REQUIRE_BODY_SELECTION' && (pendingAction.data?.candidates || []).map((name) => (
                <button key={name} onClick={() => handleActionConfirm('BODY_SELECTED', { bodyName: name })} className="px-4 py-2 text-[10px] font-bold rounded-full border border-zen-border bg-zen-surface text-zen-text-main hover:bg-zen-surface-alt transition-all">
                  {name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="text-[10px] text-zen-text-muted font-mono h-40 overflow-y-auto bg-zen-surface-alt/50 p-4 rounded-2xl border border-zen-border no-scrollbar">
          {logs.map((entry, i) => (
            <div key={i} className="mb-1 flex gap-3 opacity-80 hover:opacity-100 transition-opacity">
              <span className="text-zen-text-muted/40 shrink-0">[{new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
              <span className={entry.includes('Error') ? 'text-zen-error' : entry.includes('Done') ? 'text-zen-success font-bold' : ''}>{entry}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 zen-card border border-zen-border overflow-hidden animate-in fade-in duration-500">
      <div className="p-5 border-b border-zen-border flex items-center justify-between bg-zen-surface-alt/50">
        <div className="flex flex-col gap-1">
          <span className="zen-label text-zen-primary">BOM Classification</span>
          <span className="text-[10px] text-zen-text-muted max-w-2xl leading-relaxed">
            Verify part categories and measurement bodies before starting the engine. Drag rows to prioritize specific parts.
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 justify-end">
          <button type="button" onClick={addManualRow} className="text-[10px] font-bold px-4 py-2 rounded-full bg-zen-surface border border-zen-border hover:bg-zen-surface-alt text-zen-text-main transition-all">+ Manual Row</button>
          <div className="flex bg-zen-bg p-1 rounded-full border border-zen-border">
            <button onClick={() => selectAll(true)} className="text-[9px] px-3 py-1 text-zen-text-muted hover:text-zen-primary font-bold uppercase tracking-tighter">All</button>
            <button onClick={() => selectAll(false)} className="text-[9px] px-3 py-1 text-zen-text-muted hover:text-zen-error font-bold uppercase tracking-tighter">None</button>
          </div>
          <button onClick={startCalculation} disabled={items.filter(i => i.selected).length === 0} className="zen-pill px-6 py-2 text-[10px] disabled:opacity-30">
            Start Measure
          </button>
        </div>
      </div>

      {selectorError && (
        <div className="px-6 py-3 text-[11px] text-zen-warning bg-zen-warning/5 border-b border-zen-warning/20 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          {selectorError}
        </div>
      )}
      {bodyListError && !selectorError && (
        <div className="px-6 py-3 text-[11px] text-zen-error bg-zen-error/5 border-b border-zen-error/20 flex items-center gap-2">
           <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
           {bodyListError}
        </div>
      )}

      <div className="overflow-x-auto max-h-[55vh] overflow-y-auto no-scrollbar">
        <table className="w-full text-[11px] border-collapse min-w-max">
          <thead className="sticky top-0 bg-zen-surface z-20 border-b border-zen-border">
            <tr className="bg-zen-surface-alt/30">
              <th className="w-8 py-3 px-1"></th>
              <th className="w-8 py-3 px-2 text-center text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">In</th>
              <th className="w-8 py-3 px-1"></th>
              <th className="text-left py-3 px-4 min-w-[160px] text-[9px] font-bold text-zen-primary uppercase tracking-widest">Part Instance</th>
              <th className="text-left py-3 px-4 min-w-[200px] text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">Description</th>
              <th className="text-left py-3 px-4 min-w-[100px] text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">Type</th>
              <th className="text-left py-3 px-4 min-w-[110px] text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">Sheet</th>
              <th className="text-left py-3 px-4 min-w-[140px] text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">Material / Vendor</th>
              <th className="text-left py-3 px-4 min-w-[160px] text-[9px] font-bold text-zen-info uppercase tracking-widest">Measure Body</th>
              <th className="text-center py-3 px-4 w-16 text-[9px] font-bold text-zen-text-muted uppercase tracking-tighter">Qty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zen-border/50">
            {items.map((item, idx) => {
              const suggestions = getNameSuggestions(item)
              const datalistId = `bom-name-suggestions-${item.id}`
              const categoryOptions = item.isStd ? ['STD'] : ['Steel', 'MS', 'Casting']
              const isDragOver = dropTargetIndex === idx && dragRowIndex !== null && dragRowIndex !== idx
              return (
                <tr
                  key={item.id}
                  onDragOver={(e) => {
                    if (dragRowIndex === null) return
                    e.preventDefault()
                    e.dataTransfer.dropEffect = 'move'
                    setDropTargetIndex(idx)
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    const raw = e.dataTransfer.getData('text/plain')
                    const from = parseInt(raw, 10)
                    if (!Number.isNaN(from)) moveRow(from, idx)
                    setDragRowIndex(null)
                    setDropTargetIndex(null)
                  }}
                  className={`transition-colors duration-200 group ${item.selected ? 'bg-zen-info/[0.02]' : ''} ${
                    dragRowIndex === idx ? 'opacity-30' : ''
                  } ${isDragOver ? 'bg-zen-info/10' : 'hover:bg-zen-surface-alt/50'}`}
                >
                  <td className="py-2 px-1 align-middle text-center">
                    <span
                      role="button"
                      tabIndex={0}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(idx))
                        e.dataTransfer.effectAllowed = 'move'
                        setDragRowIndex(idx)
                      }}
                      onDragEnd={() => {
                        setDragRowIndex(null)
                        setDropTargetIndex(null)
                      }}
                      className="inline-flex cursor-grab active:cursor-grabbing text-zen-text-muted/30 group-hover:text-zen-primary p-1.5 rounded-lg hover:bg-zen-surface transition-all outline-none"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" /></svg>
                    </span>
                  </td>
                  <td className="py-2 px-2 text-center">
                    <input type="checkbox" checked={item.selected} onChange={() => toggleItem(item.id)} className="w-3.5 h-3.5 rounded border-zen-border bg-zen-bg checked:bg-zen-primary transition-all cursor-pointer" />
                  </td>
                  <td className="py-2 px-1 text-center">
                    {item.isManualRow || item.isClonedRow ? (
                      <button type="button" onClick={() => removeRow(item.id)} className="text-zen-error/40 hover:text-zen-error transition-all font-bold text-lg leading-none p-1">×</button>
                    ) : (
                      <span className="text-zen-text-muted/10 font-bold">·</span>
                    )}
                  </td>
                  <td className="py-2 px-4">
                    {item.isManualRow ? (
                      <div className="flex flex-col gap-1.5 min-w-0">
                        <input
                          type="text"
                          value={item.instanceName || ''}
                          onChange={(e) => {
                            const v = e.target.value
                            updateItem(item.id, (row) => ({ ...row, instanceName: v, instances: v.trim() ? [v.trim()] : [] }))
                          }}
                          placeholder="CATIA Instance Name"
                          className="w-full min-w-[140px] text-xs font-bold bg-zen-warning/5 border border-zen-warning/20 rounded-lg px-3 py-1.5 placeholder:text-zen-warning/30 text-zen-warning focus:bg-zen-warning/10 outline-none transition-all"
                        />
                        <input
                          type="text"
                          value={item.partNumber || ''}
                          onChange={(e) => updateItem(item.id, (row) => ({ ...row, partNumber: e.target.value }))}
                          placeholder="Part Number"
                          className="w-full text-[10px] font-mono bg-zen-surface-alt border border-zen-border rounded-md px-2 py-1 placeholder:text-zen-text-muted/30 text-zen-text-muted outline-none"
                        />
                      </div>
                    ) : (
                      <div className="flex flex-col min-w-0 group/split">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <span className="text-xs font-bold truncate text-zen-primary shrink">{item.instanceName}</span>
                          <button
                            type="button"
                            onClick={() => splitRow(item, idx)}
                            className="shrink-0 opacity-0 group-hover/split:opacity-100 flex items-center justify-center bg-zen-surface border border-zen-border hover:bg-zen-surface-alt text-zen-text-muted hover:text-zen-primary transition-all rounded p-1"
                            title="Split into multiple items"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8"/><path d="M21 3l-6 6"/><path d="M3 3l6 6"/></svg>
                          </button>
                        </div>
                        <span className="text-[10px] font-mono text-zen-text-muted/60 truncate">{item.partNumber || '—'}</span>
                        {item.isClonedRow && <span className="text-[8px] font-bold text-zen-info uppercase tracking-widest mt-0.5">Split Result</span>}
                      </div>
                    )}
                  </td>
                  <td className="py-2 px-4">
                    <input list={datalistId} type="text" value={item.description || ''} onChange={(e) => updateItem(item.id, (row) => ({ ...row, description: e.target.value }))} placeholder="Description" className="w-full bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg rounded-lg px-2 py-1.5 text-xs text-zen-text-main transition-all outline-none" />
                    <datalist id={datalistId}>{suggestions.map(s => <option key={s} value={s} />)}</datalist>
                  </td>
                  <td className="py-2 px-4">
                     <button type="button" onClick={() => updateSheetCategory(item.id, item.isStd ? 'Steel' : 'STD')} className={`text-[9px] font-bold px-3 py-1 rounded-full border tracking-widest transition-all ${item.isStd ? 'bg-zen-warning/10 text-zen-warning border-zen-warning/10' : 'bg-zen-primary text-white border-zen-primary'}`}>
                        {item.isStd ? 'STD' : 'MFG'}
                     </button>
                  </td>
                  <td className="py-2 px-4">
                     <select value={item.sheetCategory || ''} onChange={(e) => updateSheetCategory(item.id, e.target.value)} className="w-full bg-zen-surface-alt border border-zen-border rounded-lg text-[10px] font-bold px-2 py-1.5 outline-none cursor-pointer text-zen-text-main">
                        {categoryOptions.map(o => <option key={o} value={o}>{o}</option>)}
                     </select>
                  </td>
                  <td className="py-2 px-4">
                     <input type="text" value={item.isStd ? (item.manufacturer || '') : (item.material || '')} onChange={(e) => updateItem(item.id, row => ({ ...row, [item.isStd ? 'manufacturer' : 'material']: e.target.value }))} placeholder={item.isStd ? "Manufacturer" : "Material"} className="w-full bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg rounded-lg px-2 py-1.5 text-xs text-zen-text-main transition-all outline-none" />
                  </td>
                  <td className="py-2 px-4">
                     <div className="flex flex-col gap-1">
                        <div className="relative">
                           <select value={item.measurementBodyName || ''} onChange={(e) => updateMeasurementBody(item.id, e.target.value)} disabled={item.isStd || item._bodyFetchPending} className={`w-full bg-zen-info/[0.03] border border-zen-info/20 rounded-lg text-xs font-bold px-3 py-2 outline-none cursor-pointer transition-all ${item.isStd ? 'opacity-20 grayscale' : 'hover:border-zen-info'}`}>
                              <option value="">{item._bodyFetchPending ? 'Loading bodies...' : (item.bodyNameOptions?.length > 0 ? '-- Pick Body --' : '-- No Bodies Found --')}</option>
                              {(item.bodyNameOptions || []).map(o => <option key={o} value={o}>{o}</option>)}
                           </select>
                           {item._bodyFetchPending && <div className="absolute right-3 top-2.5 w-3 h-3 border-2 border-zen-info/20 border-t-zen-info rounded-full animate-spin"></div>}
                        </div>
                        {item.measureBodyColumnHint && <span className="text-[8px] font-bold text-zen-error uppercase tracking-widest ml-1">{item.measureBodyColumnHint}</span>}
                     </div>
                  </td>
                  <td className="py-2 px-4">
                     <input type="number" min="1" value={item.qty || 1} onChange={(e) => updateItem(item.id, row => ({ ...row, qty: parseInt(e.target.value, 10) || 1 }))} className="w-12 bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg rounded-lg text-center text-xs font-bold text-zen-primary transition-all outline-none" />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
