import { useState, useEffect, useRef, useMemo } from 'react'
import { flushSync } from 'react-dom'
import { startBomMeasurement } from '../utils/bomMeasurement'
import { getNameSuggestions } from '../utils/bomNaming'

const DEFAULT_METHOD = 'STL'

/** Re-apply Classify-before-measure fields onto API results (sizes/methods from server, classification from UI). */
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
    // Only update local state if the prop changed from something OTHER than our last local update
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
                // Fuzzy match against new options to avoid accidental clearance
                const mbNorm = mb.trim().toUpperCase()
                const canonicalMatch = opts.find(o => o.trim().toUpperCase() === mbNorm)
                if (canonicalMatch) {
                  mb = canonicalMatch // Use the exact name from CATIA
                }
                // If not found, we RETAIN the old value 'mb' rather than wiping it to ''
                // This ensures the backend still receives the user's preference.
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

  const updateClassification = (id, classification) => {
    setSelectorError('')
    updateItem(id, (item) => {
      if (classification === 'STD') {
        return {
          ...item,
          isStd: true,
          sheetCategory: 'STD',
          manufacturer: item.manufacturer || 'MISUMI',
        }
      }
      const nextCategory = item.sheetCategory && ['Steel', 'MS', 'Casting'].includes(item.sheetCategory) ? item.sheetCategory : 'Steel'
      return {
        ...item,
        isStd: false,
        sheetCategory: nextCategory,
      }
    })
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
    const qtyStr = window.prompt(`How many total BOM items exist under part "${item.instanceName || item.name || 'this item'}"?\n(This will create duplicate rows so you can assign a different measure body to each.)`, "2")
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
          sourceRowId: item.sourceRowId || item.id,
          measurementBodyName: '', // allow user to pick another body
          qty: 1, // assume each split body is a qty of 1 for that body
        }])[0])
      }
      next.splice(index + 1, 0, ...clones)
      return next
    })
  }

  const validateBeforeMeasurement = (selectedItems) => {
    const manualNoInstance = selectedItems.filter((item) => item.isManualRow && !`${item.instanceName || ''}`.trim())
    if (manualNoInstance.length) {
      return 'Manual row(s): enter the CATIA instance name (tree name) before measurement.'
    }
    const manualNoBody = selectedItems.filter(
      (item) =>
        item.isManualRow && !item.isStd &&
        !`${item.measurementBodyName || ''}`.trim() &&
        (item.bodyNameOptions?.length || 0) === 0,
    )
    if (manualNoBody.length) {
      return 'Manual row(s): enter the measure body name exactly as in CATIA, or wait until bodies load from the assembly.'
    }
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

    const ambiguousBody = selectedItems.filter(
      (it) => !it.isStd && (it.bodyNameOptions?.length || 0) > 1 && !`${it.measurementBodyName || ''}`.trim(),
    )
    if (ambiguousBody.length) {
      setSelectorError(
        `Choose a measure body for ${ambiguousBody.length} part(s) with multiple bodies (Measure body column).`,
      )
      return
    }

    // RESUME LOGIC: Filter out items that already have a result
    const toMeasure = selectedItems.filter(it => 
      !it.isStd && (
      !it.stock_size || 
      it.stock_size === 'Measuring...' || 
      it.stock_size === 'Unknown' ||
      it.stock_size.includes('Error') ||
      it.stock_size.includes('Not Measurable')
      )
    )

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
        console.log(`[BOMSelectionList] Action received: ${action}`, data);
        setPendingAction({ type: action, data, ws });
        onAction?.(action, data, ws);
      },
      onOpen: () => {
        if (cancelledRef.current) return
        flushSync(() => {
          setLogs((prev) => [
            ...prev,
            `Starting measurement (${measureMethod === 'STL' ? 'STL — temp part window' : 'Rough Stock'})...`,
          ])
        })
      },
      onProgress: (nextProgress) => {
        if (!cancelledRef.current) {
          flushSync(() => setProgress(nextProgress))
        }
      },
      onLog: (log) => {
        if (!cancelledRef.current) {
          flushSync(() => setLogs((prev) => [...prev, log]))
        }
      },
      onResultRow: (row) => {
        if (cancelledRef.current) return;
        setItems((prev) => prev.map(it => {
          // Match by part number and instance name
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
        setLogs((prev) => [...prev, 'Done! Finalizing results...'])
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
    e?.stopPropagation?.()
    cancelledRef.current = true
    if (wsRef.current) {
      try { wsRef.current.close() } catch (_) {}
      wsRef.current = null
    }
    setCalculating(false)
    setProgress(0)
    setLogs((prev) => (prev.length > 50 ? ['Cancelled.'] : [...prev, 'Cancelled by user.']))
  }

  const handleActionConfirm = (command, extra = {}) => {
    if (!pendingAction?.ws) return;
    pendingAction.ws.send(JSON.stringify({ command, ...extra }));
    setLogs(prev => [...prev, `✅ User confirmed: ${command} ${extra.bodyName || ''}`]);
    setPendingAction(null);
  }

  const handlePartialExport = () => {
    const measuredItems = items.filter(it => it.stock_size && it.stock_size !== 'Measuring...' && !it.stock_size.includes('Error') && !it.stock_size.includes('Not Measurable'))
    if (onPartialExport) {
        onPartialExport(measuredItems)
    }
  }

  if (calculating) {
    return (
      <div className="mt-4 p-4 rounded-xl border border-white/10 bg-black/40 space-y-4">
        <div className="flex items-center justify-between text-xs font-medium text-white/50 mb-1 gap-2">
          <span className="truncate max-w-[50%]">{logs[logs.length - 1]}</span>
          <span className="shrink-0">{progress}%</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePartialExport}
              className="shrink-0 text-[10px] font-bold px-2 py-1 rounded bg-teal-500/20 text-teal-300 border border-teal-500/40 hover:bg-teal-500/30 transition-colors"
            >
              Export Partial BOM
            </button>
            <button
              type="button"
              onClick={cancelCalculation}
              className="shrink-0 text-[10px] font-bold px-2 py-1 rounded bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
        <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full bg-white transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>

        {pendingAction && (
          <div className="p-3 rounded-lg bg-white/5 border border-amber-500/35 ring-2 ring-amber-500/30 shadow-[0_0_24px_rgba(245,158,11,0.2)] animate-pulse animate-in fade-in slide-in-from-top-2">
            <p className="text-xs font-semibold text-amber-200 mb-2 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
              Manual Action Required
            </p>
            <p className="text-[11px] text-white/70 mb-3">{pendingAction.data?.log || 'Please interact with CATIA as requested.'}</p>
            
            <div className="flex flex-wrap gap-2">
              {pendingAction.type === 'REQUIRE_AXIS_SELECTION' && (
                <button
                  onClick={() => handleActionConfirm('AXIS_CONFIRMED')}
                  className="px-4 py-2 bg-white text-black text-[11px] font-bold rounded-lg hover:bg-neutral-200 transition-all shadow-lg active:scale-95 flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  Confirm Axis Selected
                </button>
              )}
              {pendingAction.type === 'REQUIRE_BODY_SELECTION' && (pendingAction.data?.candidates || []).map((name) => (
                <button
                  key={name}
                  onClick={() => handleActionConfirm('BODY_SELECTED', { bodyName: name })}
                  className="px-3 py-1.5 text-[11px] font-medium rounded-lg border transition-all active:scale-95 bg-white/5 text-white/80 border-white/15 hover:bg-white/10"
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        )}

        <p className="text-[10px] text-white/30">First part may take time. You can Cancel to stop.</p>
        <div className="text-[10px] text-white/40 font-mono h-32 overflow-y-auto bg-black/40 p-2 rounded border border-white/5 custom-scrollbar">
          {logs.map((entry, i) => (
            <div key={i} className="mb-0.5 leading-relaxed">
              <span className="opacity-30 mr-2">[{new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
              {entry}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 rounded-xl border border-white/10 bg-black/20 overflow-hidden">
      <div className="p-3 border-b border-white/10 flex items-center justify-between bg-white/5">
        <div className="flex flex-col">
          <span className="text-xs font-semibold text-white/70">Classify Parts Before Measuring</span>
          <span className="text-[10px] mt-1 text-white/40">
            Drag the grip on the left to reorder rows (measurement runs top to bottom). Choose MFG/STD, route MFG rows into Steel/MS/Casting, rename parts, and pick a measure body when more than one exists. Use Add manual row for a missed part: instance name as in the tree, optional part number, and exact measure body name when bodies do not load. Material (Steel Type) can be filled here or later in the editor.
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 justify-end">
          {items.some(it => it.stock_size && it.stock_size !== 'Measuring... && !it.stock_size.includes("Error")') && (
            <button
              onClick={handlePartialExport}
              className="text-[10px] font-semibold px-2 py-1 rounded-md bg-teal-500/20 text-teal-300 border border-teal-500/40 hover:bg-teal-500/30 transition-colors"
            >
              Export Results So Far
            </button>
          )}
          <button
            type="button"
            onClick={addManualRow}
            className="text-[10px] font-semibold px-2 py-1 rounded-md bg-white/10 text-white/90 border border-white/15 hover:bg-white/15 transition-colors"
          >
            Add manual row
          </button>
          <button onClick={() => selectAll(true)} className="text-[10px] text-white/40 hover:text-white transition-colors">Select All</button>
          <span className="text-white/10">|</span>
          <button onClick={() => selectAll(false)} className="text-[10px] text-white/40 hover:text-white transition-colors">None</button>
        </div>
      </div>

      {selectorError && (
        <div className="px-3 py-2 text-[11px] text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
          {selectorError}
        </div>
      )}
      {bodyListError && !selectorError && (
        <div className="px-3 py-2 text-[11px] text-rose-300/90 bg-rose-500/10 border-b border-rose-500/20">
          {bodyListError}
        </div>
      )}

      <div className="overflow-x-auto max-h-[55vh] overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-black/50 z-10">
            <tr className="border-b border-white/10">
              <th className="text-left py-2 px-1 w-7" title="Drag to reorder"> </th>
              <th className="text-left py-2 px-2 w-8">In</th>
              <th className="text-left py-2 px-2 w-8" aria-label="Remove manual row" />
              <th className="text-left py-2 px-2 min-w-[150px]">Instance</th>
              <th className="text-left py-2 px-2 min-w-[180px]">Rename / Description</th>
              <th className="text-left py-2 px-2 min-w-[100px]">Type</th>
              <th className="text-left py-2 px-2 min-w-[110px]">Sheet</th>
              <th className="text-left py-2 px-2 min-w-[120px]">Material / Vendor</th>
              <th className="text-left py-2 px-2 min-w-[140px]">Measure body</th>
              <th className="text-left py-2 px-2 w-16">Qty</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const suggestions = getNameSuggestions(item)
              const datalistId = `bom-name-suggestions-${item.id}`
              const classification = item.isStd ? 'STD' : 'MFG'
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
                  className={`border-b border-white/5 transition-colors ${item.selected ? 'bg-white/[0.03]' : ''} ${
                    dragRowIndex === idx ? 'opacity-50' : ''
                  } ${isDragOver ? 'bg-sky-500/15 ring-1 ring-inset ring-sky-400/40' : ''}`}
                >
                  <td className="py-2 px-1 align-middle w-7">
                    <span
                      role="button"
                      tabIndex={0}
                      draggable
                      title="Drag to reorder"
                      aria-label="Drag row to reorder"
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(idx))
                        e.dataTransfer.effectAllowed = 'move'
                        setDragRowIndex(idx)
                      }}
                      onDragEnd={() => {
                        setDragRowIndex(null)
                        setDropTargetIndex(null)
                      }}
                      className="inline-flex cursor-grab active:cursor-grabbing text-white/35 hover:text-white/70 p-0.5 rounded hover:bg-white/10 outline-none focus-visible:ring-1 focus-visible:ring-white/40"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                        <circle cx="9" cy="6" r="1.35" />
                        <circle cx="15" cy="6" r="1.35" />
                        <circle cx="9" cy="12" r="1.35" />
                        <circle cx="15" cy="12" r="1.35" />
                        <circle cx="9" cy="18" r="1.35" />
                        <circle cx="15" cy="18" r="1.35" />
                      </svg>
                    </span>
                  </td>
                  <td className="py-2 px-2">
                    <input type="checkbox" checked={item.selected} onChange={() => toggleItem(item.id)} className="rounded border-white/20" />
                  </td>
                  <td className="py-2 px-2 align-top">
                    {item.isManualRow || item.isClonedRow ? (
                      <button
                        type="button"
                        title="Remove this row"
                        onClick={() => removeRow(item.id)}
                        className="text-[10px] text-rose-300/90 hover:text-rose-200 px-1"
                      >
                        ×
                      </button>
                    ) : (
                      <span className="text-white/15 select-none">·</span>
                    )}
                  </td>
                  <td className="py-2 px-2">
                    {item.isManualRow ? (
                      <div className="flex flex-col gap-1 min-w-0">
                        <input
                          type="text"
                          value={item.instanceName || ''}
                          onChange={(e) => {
                            const v = e.target.value
                            updateItem(item.id, (row) => ({
                              ...row,
                              instanceName: v,
                              instances: v.trim() ? [v.trim()] : [],
                            }))
                          }}
                          placeholder="CATIA instance name"
                          className="w-full min-w-[140px] text-[11px] bg-amber-500/10 border border-amber-500/25 rounded px-2 py-1 placeholder:text-white/35"
                        />
                        <input
                          type="text"
                          value={item.partNumber || ''}
                          onChange={(e) => updateItem(item.id, (row) => ({ ...row, partNumber: e.target.value }))}
                          placeholder="Part number (optional, helps resolve)"
                          className="w-full text-[10px] font-mono bg-white/5 border border-white/10 rounded px-2 py-0.5 placeholder:text-white/30"
                        />
                      </div>
                    ) : (
                      <div className="flex flex-col min-w-0 group">
                        <div className="flex items-center gap-1.5 overflow-hidden">
                          <span className="text-xs font-semibold truncate text-white/90 shrink">{item.instanceName}</span>
                          <button
                            type="button"
                            onClick={() => splitRow(item, idx)}
                            className="shrink-0 opacity-0 group-hover:opacity-100 flex items-center justify-center bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-all rounded w-4 h-4"
                            title="Split into multiple items for this part"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8"/><path d="M21 3l-6 6"/><path d="M3 3l6 6"/></svg>
                          </button>
                        </div>
                        <span className="text-[10px] font-mono opacity-50 truncate">{item.name}</span>
                      </div>
                    )}
                  </td>
                  <td className="py-2 px-2">
                    <input
                      list={datalistId}
                      type="text"
                      value={item.description || ''}
                      onChange={(e) => updateItem(item.id, (row) => ({ ...row, description: e.target.value }))}
                      className="w-full min-w-[160px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
                    />
                    <datalist id={datalistId}>
                      {suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
                    </datalist>
                  </td>
                  <td className="py-2 px-2">
                    <select value={classification} onChange={(e) => updateClassification(item.id, e.target.value)} className="w-full min-w-[80px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1">
                      <option value="MFG">MFG</option>
                      <option value="STD">STD</option>
                    </select>
                  </td>
                  <td className="py-2 px-2">
                    <select value={item.sheetCategory || ''} onChange={(e) => updateSheetCategory(item.id, e.target.value)} className="w-full min-w-[96px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1">
                      {categoryOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  </td>
                  <td className="py-2 px-2">
                    <input
                      type="text"
                      value={item.isStd ? (item.manufacturer || '') : (item.material || '')}
                      onChange={(e) => updateItem(item.id, (row) => ({ ...row, [row.isStd ? 'manufacturer' : 'material']: e.target.value }))}
                      placeholder={item.isStd ? 'MISUMI / Vendor' : 'Optional at this step'}
                      className={`w-full min-w-[120px] text-[11px] border rounded px-2 py-1 bg-white/5 border-white/10`}
                    />
                  </td>
                  <td className="py-2 px-2 align-top">
                    {!item.selected ? (
                      <span className="text-white/25 text-[10px]">—</span>
                    ) : item._bodyFetchPending ? (
                      <span className="text-white/35 text-[10px]">Loading…</span>
                    ) : item.isManualRow && (item.bodyNameOptions?.length || 0) === 0 ? (
                      <input
                        type="text"
                        value={item.measurementBodyName || ''}
                        onChange={(e) => updateMeasurementBody(item.id, e.target.value)}
                        placeholder="Exact body name in CATIA"
                        className="w-full max-w-[200px] text-[10px] bg-amber-500/10 border border-amber-500/25 rounded px-2 py-1 placeholder:text-white/35"
                      />
                    ) : (item.bodyNameOptions?.length || 0) === 0 ? (
                      <span
                        className="text-rose-300/85 text-[10px] leading-snug block max-w-[168px]"
                        title={item.measureBodyColumnHint || 'No bodies loaded'}
                      >
                        {item.measureBodyColumnHint || '—'}
                      </span>
                    ) : (item.bodyNameOptions?.length || 0) === 1 ? (
                      <span className="text-[10px] text-white/60 font-mono truncate block max-w-[160px]" title={item.bodyNameOptions[0]}>
                        {item.bodyNameOptions[0]}
                      </span>
                    ) : (
                      <select
                        value={item.measurementBodyName || ''}
                        onChange={(e) => updateMeasurementBody(item.id, e.target.value)}
                        className="w-full max-w-[180px] text-[10px] bg-white/5 border border-white/10 rounded px-2 py-1"
                      >
                        <option value="">Auto (BOM name match)</option>
                        {item.bodyNameOptions.map((bn) => (
                          <option key={bn} value={bn}>
                            {bn}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td className="py-2 px-2 text-white/60">{item.qty || 1}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="p-3 border-t border-white/10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] text-white/40 uppercase tracking-wide">Measure with</span>
          <button
            type="button"
            onClick={() => setMeasureMethod('STL')}
            className={`text-[11px] font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
              measureMethod === 'STL'
                ? 'bg-emerald-500/25 text-emerald-200 border-emerald-500/50'
                : 'bg-white/5 text-white/50 border-white/10 hover:border-white/25'
            }`}
          >
            STL (default)
          </button>
          <button
            type="button"
            onClick={() => setMeasureMethod('ROUGH_STOCK')}
            className={`text-[11px] font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
              measureMethod === 'ROUGH_STOCK'
                ? 'bg-amber-500/25 text-amber-200 border-amber-500/50'
                : 'bg-white/5 text-white/50 border-white/10 hover:border-white/25'
            }`}
          >
            Rough Stock
          </button>
        </div>
        <button
          onClick={startCalculation}
          className="bg-white text-black text-xs font-bold px-4 py-2 rounded-lg hover:bg-neutral-200 transition-all active:scale-95 flex items-center gap-2 shrink-0"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          Calculate dimensions
        </button>
      </div>
    </div>
  )
}
