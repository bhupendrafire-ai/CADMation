import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { flushSync } from 'react-dom'
import { DataGrid, SelectColumn } from 'react-data-grid'
import 'react-data-grid/lib/styles.css'
import { startBomMeasurement } from '../utils/bomMeasurement'
import { getNameSuggestions } from '../utils/bomNaming'

const DEFAULT_METHOD = 'ROUGH_STOCK'

const textEditor = ({ row, column, onRowChange, onClose }) => {
  return (
    <input
      autoFocus
      className="rdg-text-editor"
      value={row[column.key]}
      onChange={(e) => onRowChange({ ...row, [column.key]: e.target.value }, true)}
      onBlur={() => onClose(true)}
    />
  )
}

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
  const [force, setForce] = useState(false)
  const [selectedRows, setSelectedRows] = useState(() => new Set(items.filter(it => it.selected).map(it => it.id)))
  
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
      setSelectedRows(new Set(nextNormalized.filter(it => it.selected).map(it => it.id)))
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

  // Sync selectedRows to item.selected
  useEffect(() => {
    setItems(prev => prev.map(it => ({
      ...it,
      selected: selectedRows.has(it.id)
    })));
  }, [selectedRows]);

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
        isClonedRow: !!i.isClonedRow,
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
              ? 'Not found — open the CATProduct'
              : e === 'no_bodies'
                ? 'No bodies'
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
                  measureBodyColumnHint: 'No match',
                }
              }
              const opts = Array.isArray(r.bodies) ? r.bodies : []
              let mb = row.measurementBodyName || ''
              
              if (opts.length === 1) {
                mb = opts[0]
              } else if (opts.length > 1 && mb) {
                const mbNorm = mb.trim().toUpperCase()
                const canonicalMatch = opts.find(o => o.trim().toUpperCase() === mbNorm)
                if (canonicalMatch) mb = canonicalMatch
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

  const handleRowsChange = useCallback((newRows, { indexes, column }) => {
    setSelectorError('')
    const nextItems = [...items]
    indexes.forEach(idx => {
      const gridRow = newRows[idx]
      const originalIndex = items.findIndex(it => it.id === gridRow.id)
      if (originalIndex === -1) return

      let updatedRow = { ...gridRow }
      
      if (column.key === 'isStd') {
        updatedRow.sheetCategory = updatedRow.isStd ? 'STD' : 'Steel';
        updatedRow.manufacturer = updatedRow.isStd ? (updatedRow.manufacturer || 'MISUMI') : updatedRow.manufacturer;
      }
      
      if (column.key === 'sheetCategory') {
        updatedRow.isStd = updatedRow.sheetCategory === 'STD';
        if (updatedRow.isStd) updatedRow.manufacturer = updatedRow.manufacturer || 'MISUMI';
      }

      nextItems[originalIndex] = updatedRow
    })
    setItems(nextItems)
  }, [items]);

  const selectAll = (selected) => {
    setSelectorError('')
    if (selected) {
      setSelectedRows(new Set(items.map(it => it.id)))
    } else {
      setSelectedRows(new Set())
    }
  }

  const addManualRow = () => {
    setSelectorError('')
    const sid = newManualRowId()
    const newRow = normalizeRows([
      {
        isManualRow: true,
        id: sid,
        sourceRowId: sid,
        partNumber: '',
        instanceName: 'NEW_PART',
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
    ])[0];
    setItems(prev => [...prev, newRow]);
    setSelectedRows(prev => new Set([...prev, sid]));
  }

  const removeRow = (id) => {
    setSelectorError('')
    setItems((prev) => prev.filter((row) => row.id !== id))
    setSelectedRows(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  const splitRow = (row) => {
    const qtyStr = window.prompt(`How many total BOM items exist under part "${row.instanceName || row.name || 'this item'}"?`, "2")
    if (!qtyStr) return
    const count = parseInt(qtyStr, 10)
    if (isNaN(count) || count <= 1) return

    setItems(prev => {
      const next = [...prev]
      const index = next.findIndex(it => it.id === row.id)
      const clones = []
      for (let i = 1; i < count; i++) {
        const sid = newManualRowId()
        clones.push(normalizeRows([{
          ...row,
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

  const startCalculation = () => {
    const selectedItems = items.filter((item) => item.selected)
    if (selectedItems.length === 0) return

    const ambiguousBody = selectedItems.filter(it => !it.isStd && (it.bodyNameOptions?.length || 0) > 1 && !`${it.measurementBodyName || ''}`.trim())
    if (ambiguousBody.length) {
      setSelectorError(`Choose a measure body for ${ambiguousBody.length} part(s).`)
      return
    }

    const toMeasure = force 
      ? selectedItems.filter(it => !it.isStd)
      : selectedItems.filter(it => !it.isStd && (!it.stock_size || it.stock_size === 'Measuring...' || it.stock_size === 'Unknown' || it.stock_size.includes('Error')))

    setCalculating(true)
    setProgress(0)
    setLogs(['Connecting to engine...'])
    setSelectorError('')
    setPendingAction(null)
    cancelledRef.current = false

    if (toMeasure.length === 0) {
      setLogs(prev => [...prev, 'All selected items already measured.'])
      setCalculating(false)
      return
    }

    const ws = startBomMeasurement({
      items: toMeasure,
      projectName,
      method: measureMethod,
      force,
      tempRenameDuplicateBodies: !!bomOptions?.tempRenameDuplicateBodies,
      onAction: (action, data, ws) => {
        setPendingAction({ type: action, data, ws });
        onAction?.(action, data, ws);
      },
      onOpen: () => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, `Starting measurement (${measureMethod})...`])
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
          const rowId = row.id || row.itemId;
          if (it.id === rowId) {
            return {
              ...it,
              stock_size: row.stock_size !== undefined ? row.stock_size : it.stock_size,
              done: row.isPartial ? it.done : (row.done || true)
            };
          }
          return it;
        }));
      },
      onDone: (data) => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, `Done! Finalizing...`])
        setTimeout(() => {
          const merged = mergeClassificationIntoResults(itemsRef.current, data.results || [])
          onCalculationComplete?.({ results: merged, retryCandidates: data.retryCandidates || [] })
        }, 1000)
      },
      onError: (error) => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, `Error: ${error}`])
        setCalculating(false)
      },
    })
    wsRef.current = ws
  }

  const cancelCalculation = () => {
    cancelledRef.current = true
    if (wsRef.current) wsRef.current.close()
    setCalculating(false)
    setProgress(0)
  }

  const columns = useMemo(() => [
    { ...SelectColumn, width: 35 },
    { 
        key: '_drag', 
        name: '', 
        width: 30, 
        renderCell: () => <div className="flex items-center justify-center text-zen-text-muted/30 cursor-grab active:cursor-grabbing"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg></div> 
    },
    { 
        key: 'instanceName', 
        name: 'Part Instance', 
        width: 180, 
        resizable: true,
        cellClass: 'editable-cell',
        renderEditCell: textEditor,
        renderCell: ({ row }) => (
            <div className="flex items-center gap-2 overflow-hidden">
                <span className={`text-[10px] font-bold truncate ${row.isManualRow ? 'text-zen-warning' : 'text-zen-primary'}`}>
                    {row.instanceName}
                </span>
                <span className="text-[9px] font-mono text-zen-text-muted/50 truncate">
                    ({row.partNumber || '—'})
                </span>
                {row.isClonedRow && <span className="text-[7px] font-bold text-zen-info uppercase tracking-widest shrink-0">Split</span>}
            </div>
        )
    },
    { key: 'description', name: 'Description', width: 160, resizable: true, cellClass: 'editable-cell', renderEditCell: textEditor },
    { 
        key: 'isStd', 
        name: 'Type', 
        width: 60, 
        renderCell: ({ row }) => {
            const isStd = !!row.isStd;
            return (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', width: '100%' }}>
                    <div style={{
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '1px 6px',
                        borderRadius: '3px',
                        border: `1px solid ${isStd ? '#FDE68A' : '#18181b'}`,
                        backgroundColor: isStd ? '#FFF7ED' : '#18181b',
                        color: isStd ? '#D97706' : '#ffffff',
                        textAlign: 'center',
                        minWidth: '36px',
                        lineHeight: '1',
                        display: 'inline-block'
                    }}>
                        {isStd ? 'STD' : 'MFG'}
                    </div>
                </div>
            );
        }
    },
    { 
        key: 'sheetCategory', 
        name: 'Sheet', 
        width: 80, 
        resizable: true, 
        cellClass: 'editable-cell dropdown-cell',
        renderEditCell: ({ row, onRowChange }) => (
            <select value={row.sheetCategory || ''} onChange={(e) => onRowChange({ ...row, sheetCategory: e.target.value })} className="w-full bg-zen-surface text-[10px] h-full outline-none" autoFocus>
                {(row.isStd ? ['STD'] : ['Steel', 'MS', 'Casting']).map(o => <option key={o} value={o}>{o}</option>)}
            </select>
        )
    },
    { key: 'material', name: 'Material / Vendor', width: 130, resizable: true, cellClass: 'editable-cell', renderEditCell: textEditor },
    { 
        key: 'measurementBodyName', 
        name: 'Measure Body', 
        width: 200, 
        resizable: true, 
        cellClass: 'editable-cell dropdown-cell',
        renderEditCell: ({ row, onRowChange }) => (
            <select value={row.measurementBodyName || ''} onChange={(e) => onRowChange({ ...row, measurementBodyName: e.target.value })} className="w-full bg-zen-surface text-[10px] h-full outline-none" autoFocus>
                <option value="">-- Pick Body --</option>
                {(row.bodyNameOptions || []).map(o => <option key={o} value={o}>{o}</option>)}
            </select>
        ),
        renderCell: ({ row }) => (
            <div className="flex flex-col justify-center h-full gap-0.5 leading-none">
                <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold ${row.measurementBodyName ? 'text-zen-info' : 'text-zen-text-muted'}`}>
                        {row.measurementBodyName || (row.isStd ? '—' : 'Select...')}
                    </span>
                    {row._bodyFetchPending && <div className="w-2.5 h-2.5 border border-zen-info/20 border-t-zen-info rounded-full animate-spin"></div>}
                </div>
                {row.measureBodyColumnHint && <span className="text-[7px] font-bold text-zen-error uppercase tracking-widest">{row.measureBodyColumnHint}</span>}
            </div>
        )
    },
    { key: 'qty', name: 'Qty', width: 45, resizable: true, cellClass: 'editable-cell text-center', renderEditCell: textEditor },
    {
        key: '_actions',
        name: '',
        width: 60,
        renderCell: ({ row }) => (
            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity justify-end pr-2">
                {!row.isManualRow && !row.isClonedRow && (
                    <button onClick={() => splitRow(row)} className="p-1 hover:bg-zen-surface-alt rounded text-zen-text-muted hover:text-zen-primary transition-all" title="Split">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8"/><path d="M21 3l-6 6"/><path d="M3 3l6 6"/></svg>
                    </button>
                )}
                {(row.isManualRow || row.isClonedRow) && (
                    <button onClick={() => removeRow(row.id)} className="p-1 hover:bg-zen-error/10 rounded text-zen-error/40 hover:text-zen-error transition-all font-bold">×</button>
                )}
            </div>
        )
    }
  ], [items, handleRowsChange]);

  const mfgCount = items.filter(it => !it.isStd).length;
  const stdCount = items.filter(it => it.isStd).length;

  if (calculating) {
    return (
      <div className="mt-4 p-6 zen-card border border-zen-border space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="zen-label text-zen-primary uppercase tracking-widest">Measure Progress</span>
            <span className="text-[10px] text-zen-text-muted mt-1 truncate max-w-[300px] font-mono">{logs[logs.length - 1]}</span>
          </div>
          <div className="flex items-center gap-3">
             <span className="text-xl font-bold text-zen-primary">{progress}%</span>
             <button type="button" onClick={cancelCalculation} className="text-[10px] font-bold px-4 py-2 rounded-full bg-zen-error/10 text-zen-error border border-zen-error/20 hover:bg-zen-error/20">Cancel</button>
          </div>
        </div>
        <div className="w-full h-1.5 bg-zen-surface-alt rounded-full overflow-hidden border border-zen-border/50">
          <div className="h-full bg-zen-primary transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
        </div>
        <div className="text-[10px] text-zen-text-muted font-mono h-40 overflow-y-auto bg-zen-surface-alt/50 p-4 rounded-2xl border border-zen-border no-scrollbar">
          {logs.map((entry, i) => <div key={i} className="mb-1">[{new Date().toLocaleTimeString()}] {entry}</div>)}
          <div ref={logEndRef} />
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4 zen-card border border-zen-border overflow-hidden flex flex-col min-h-[500px]">
      <div className="p-4 border-b border-zen-border flex items-center justify-between bg-zen-surface-alt/30">
        <div className="flex items-center gap-6">
          <div className="flex flex-col">
            <span className="zen-label text-zen-primary">Initial Draft</span>
            <div className="flex items-center gap-2 mt-1">
                <span className="text-[9px] px-2 py-0.5 rounded-md bg-zen-info/10 text-zen-info border border-zen-info/10 font-bold uppercase tracking-wider">MFG: {mfgCount}</span>
                <span className="text-[9px] px-2 py-0.5 rounded-md bg-zen-warning/10 text-zen-warning border border-zen-warning/10 font-bold uppercase tracking-wider">STD: {stdCount}</span>
            </div>
          </div>
          
          <div className="h-8 w-px bg-zen-border"></div>

          <div className="flex bg-zen-bg p-1 rounded-full border border-zen-border">
            <button onClick={() => selectAll(true)} className="text-[9px] px-3 py-1 text-zen-text-muted hover:text-zen-primary font-bold uppercase tracking-tighter">All</button>
            <button onClick={() => selectAll(false)} className="text-[9px] px-3 py-1 text-zen-text-muted hover:text-zen-error font-bold uppercase tracking-tighter">None</button>
          </div>

          <div className="flex bg-zen-bg p-1 rounded-full border border-zen-border">
             <button onClick={() => setMeasureMethod('STL')} className={`text-[9px] px-4 py-1 rounded-full transition-all font-bold uppercase tracking-tighter ${measureMethod === 'STL' ? 'bg-zen-primary text-white' : 'text-zen-text-muted hover:text-zen-primary'}`}>STL</button>
             <button onClick={() => setMeasureMethod('ROUGH_STOCK')} className={`text-[9px] px-4 py-1 rounded-full transition-all font-bold uppercase tracking-tighter ${measureMethod === 'ROUGH_STOCK' ? 'bg-zen-primary text-white' : 'text-zen-text-muted hover:text-zen-primary'}`}>Rough Stock</button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={() => setForce(!force)} className={`text-[9px] px-4 py-2 rounded-full border font-bold uppercase tracking-tighter transition-all ${force ? 'bg-zen-warning/10 text-zen-warning border-zen-warning/30' : 'bg-zen-bg text-zen-text-muted border-zen-border hover:text-zen-primary'}`}>Force Re-measure</button>
          <button type="button" onClick={addManualRow} className="text-[10px] font-bold px-4 py-2 rounded-full bg-zen-surface border border-zen-border hover:bg-zen-surface-alt text-zen-text-main transition-all">+ Manual Row</button>
          <button onClick={startCalculation} disabled={selectedRows.size === 0} className="zen-pill px-6 py-2 text-[10px] disabled:opacity-30">Start Measure</button>
        </div>
      </div>

      {selectorError && <div className="px-6 py-2 text-[11px] text-zen-warning bg-zen-warning/5 border-b border-zen-warning/20">{selectorError}</div>}
      {bodyListError && <div className="px-6 py-2 text-[11px] text-zen-error bg-zen-error/5 border-b border-zen-error/20">{bodyListError}</div>}

      <div className="flex-1 overflow-hidden rdg-zen-container">
        <DataGrid
          columns={columns}
          rows={items}
          onRowsChange={handleRowsChange}
          rowKeyGetter={(row) => row.id}
          selectedRows={selectedRows}
          onSelectedRowsChange={setSelectedRows}
          onCellClick={({ row, column, selectCell }) => {
            if (column.key === 'isStd') {
              const rowIndex = items.findIndex(it => it.id === row.id);
              if (rowIndex === -1) return;
              const nextItems = items.map((it, idx) => idx === rowIndex ? { ...it, isStd: !it.isStd } : it);
              handleRowsChange(nextItems, { indexes: [rowIndex], column: { key: 'isStd' } });
            } else if (column.renderEditCell) {
              selectCell(true);
            }
          }}
          rowHeight={35}
          headerRowHeight={35}
          className="rdg-light fill-grid"
          style={{ height: '100%' }}
        />
      </div>
    </div>
  )
}
