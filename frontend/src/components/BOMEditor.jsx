import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { getNameSuggestions } from '../utils/bomNaming'

function parseSize(sizeStr) {
  if (!sizeStr || typeof sizeStr !== 'string') return { kind: 'empty', l: '', w: '', h: '', values: [] }
  const normalized = sizeStr.trim()
  const numbers = normalized.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || []
  if (/(?:\bDIA\b|\bDIAMETER\b|Ø)/i.test(normalized) && numbers.length >= 2) {
    return { kind: 'diameter', l: `DIA ${numbers[0]}`, w: '', h: `${numbers[1]}`, values: [numbers[0], numbers[1]] }
  }
  if (numbers.length >= 3) {
    return { kind: 'box', l: `${numbers[0]}`, w: `${numbers[1]}`, h: `${numbers[2]}`, values: [numbers[0], numbers[1], numbers[2]] }
  }
  return { kind: 'raw', l: normalized, w: '', h: '', values: [] }
}

function formatSizeFromCells(l, w, h) {
  const left = `${l || ''}`.trim()
  const middle = `${w || ''}`.trim()
  const right = `${h || ''}`.trim()
  if (!left && !middle && !right) return ''
  const diaMatch = left.match(/(?:DIA|DIAMETER|Ø)\s*(-?\d+(?:\.\d+)?)/i)
  if (diaMatch && right) return `DIA ${diaMatch[1]} x ${right}`
  if (left && middle && right) return `${left} x ${middle} x ${right}`
  return [left, middle, right].filter(Boolean).join(' x ')
}

function computeRmSize(sizeStr, machiningStock = 0, roundingMm = 0) {
  const dims = parseSize(sizeStr)
  if (dims.kind === 'empty') return '—'
  const add = Number(machiningStock) || 0
  const step = Number(roundingMm) || 1
  const roundDim = (d) => (step > 0 ? Math.round((d + add) / step) * step : d + add)
  if (dims.kind === 'diameter' && dims.values.length >= 2) {
    return `DIA ${roundDim(dims.values[0])} x ${roundDim(dims.values[1])}`
  }
  if (dims.kind === 'box' && dims.values.length >= 3) {
    return dims.values.map(roundDim).join(' x ')
  }
  return sizeStr || '—'
}

function normalizeFlags(flags) {
  if (Array.isArray(flags)) return flags
  if (typeof flags === 'string' && flags.trim()) return flags.split(',').map((flag) => flag.trim()).filter(Boolean)
  return []
}

function deriveReviewStatus(row) {
  if (row.reviewStatus) return row.reviewStatus
  if (normalizeFlags(row.validationFlags).length) return 'needs_review'
  return 'approved'
}

function normalizeRows(list) {
  return (list || []).map((row, i) => {
    const millingSize = row.millingSize || row.size || ''
    const rmSize = row.rmSize || computeRmSize(millingSize, row.machiningStock, row.roundingMm)
    const incomingCategory = row.sheetCategory || row.exportBucket || ''
    const sheetCategory = (row.isStd || incomingCategory.startsWith('STD'))
      ? 'STD'
      : (['Steel', 'MS', 'Casting'].includes(incomingCategory) ? incomingCategory : 'Steel')
    const reviewStatus = deriveReviewStatus({ ...row, sheetCategory })
    return {
      ...row,
      selected: row.selected !== false,
      keepInExport: row.keepInExport !== false && row.selected !== false,
      isStd: row.isStd || sheetCategory === 'STD',
      qty: Number(row.qty) || 1,
      machiningStock: Number(row.machiningStock) || 0,
      roundingMm: Number(row.roundingMm) || 0,
      description: row.description || '',
      sheetCategory,
      exportBucket: row.exportBucket || sheetCategory,
      material: row.material || '',
      manufacturer: row.manufacturer || '',
      catalogCode: row.catalogCode || '',
      remark: row.remark || '',
      methodUsed: row.methodUsed || 'UNKNOWN',
      measurementConfidence: row.measurementConfidence || 'low',
      reviewStatus,
      discrepancyType: row.discrepancyType || '',
      reviewNote: row.reviewNote || '',
      millingSize,
      size: millingSize,
      rmSize,
      validationFlags: normalizeFlags(row.validationFlags),
      sourceRowId: row.sourceRowId || `${row.partNumber || row.name || i}|${row.instanceName || ''}`,
      _rowId: row._rowId ?? row.id ?? i + 1,
      parentAssembly: row.parentAssembly || '',
      includeIn2dDrawing: row.includeIn2dDrawing === true,
      draftingAxisName: row.draftingAxisName || '',
    }
  })
}

const sheetOptions = ['Steel', 'MS', 'Casting', 'STD']
const reviewOptions = ['approved', 'needs_review', 'corrected', 'extra']
const discrepancyOptions = ['', 'uncertain', 'measurement_failed', 'wrong_data', 'extra', 'duplicate']
const filterOptions = [
  { id: 'all', label: 'All' },
  { id: 'needs_review', label: 'Needs Review' },
  { id: 'approved', label: 'Approved' },
]

export default function BOMEditor({ items: initialItems, projectName, onItemsChange, onExport, disabled, isFullscreen }) {
  const [items, setItems] = useState(() => normalizeRows(initialItems))
  const [bulkStock, setBulkStock] = useState('')
  const [bulkRounding, setBulkRounding] = useState('5')
  const [activeFilter, setActiveFilter] = useState('all')
  const [exportError, setExportError] = useState('')
  const [draft2dLoading, setDraft2dLoading] = useState(false)
  const [draft2dFeedback, setDraft2dFeedback] = useState('')
  const [globalDraftingAxisName, setGlobalDraftingAxisName] = useState('')
  const [axisPreviewLoading, setAxisPreviewLoading] = useState(false)
  const [axisPreviewOk, setAxisPreviewOk] = useState(false)
  const [axisPreviewUsedSelection, setAxisPreviewUsedSelection] = useState(false)
  const [axisPropagateLoading, setAxisPropagateLoading] = useState(false)
  const [draggingRowId, setDraggingRowId] = useState(null)
  const [dropTargetRowId, setDropTargetRowId] = useState(null)
  const [showTechnicalColumns, setShowTechnicalColumns] = useState(false)
  const [isDraftingSidebarOpen, setIsDraftingSidebarOpen] = useState(false)
  const [isCompactView, setIsCompactView] = useState(true)
  const [showBulkActions, setShowBulkActions] = useState(false)

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
    setAxisPreviewOk(false)
  }, [globalDraftingAxisName])

  const updateItems = useCallback((updater) => {
    setItems((prev) => {
      const next = normalizeRows(typeof updater === 'function' ? updater(prev) : updater)
      setExportError('')
      
      // Sync to parent
      const nextJson = JSON.stringify(next)
      if (nextJson !== lastSyncedItemsRef.current) {
        lastSyncedItemsRef.current = nextJson
        // Use a small timeout to debounce the parent update and prevent the "ping-pong" re-render frenzy
        const timer = setTimeout(() => onItemsChange?.(next), 0)
        return next
      }
      return next
    })
  }, [onItemsChange])

  const updateRow = useCallback((rowIndex, field, value) => {
    updateItems((prev) => prev.map((row, i) => {
      if (i !== rowIndex) return row
      const next = { ...row, [field]: value }

      // PERSISTENCE SYNC: Save categorisation or measurement choice instantly
      if (['isStd', 'sheetCategory', 'measurementBodyName', 'description', 'partNumber'].includes(field)) {
        fetch('/api/catia/bom/cache_edit', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({
             projectName: projectName || 'DEFAULT',
             instanceName: next.instanceName,
             data: { [field]: value } // Save the specific field change
           })
        }).catch(err => console.error("Persistence sync failed:", err))
      }

      if (field === 'selected') next.keepInExport = value
      if (field === 'keepInExport') next.selected = value
      if (field === 'sheetCategory') {
        next.exportBucket = value
        next.isStd = value === 'STD'
        if (value === 'STD' && !next.manufacturer) next.manufacturer = 'MISUMI'
      }
      if (field === 'isStd') {
        next.sheetCategory = value ? 'STD' : (['Steel', 'MS', 'Casting'].includes(row.sheetCategory) ? row.sheetCategory : 'Steel')
        next.exportBucket = next.sheetCategory
        if (value && !next.manufacturer) next.manufacturer = 'MISUMI'
      }
      return next
    }))
  }, [updateItems])

  const updateMillingCell = useCallback((rowIndex, cell, value) => {
    updateItems((prev) => prev.map((row, i) => {
      if (i !== rowIndex) return row
      const dims = parseSize(row.millingSize || row.size)
      const nextDims = { l: dims.l, w: dims.w, h: dims.h, [cell]: value }
      const millingSize = formatSizeFromCells(nextDims.l, nextDims.w, nextDims.h)
      return {
        ...row,
        millingSize,
        size: millingSize,
        rmSize: computeRmSize(millingSize, row.machiningStock, row.roundingMm),
      }
    }))
  }, [updateItems])

  const setAllSelected = useCallback((selected) => {
    updateItems((prev) => prev.map((row) => ({ ...row, selected, keepInExport: selected })))
  }, [updateItems])

  const addMachiningStockToAll = useCallback((stock, rounding) => {
    const stockNum = Number(stock) || 0
    const roundNum = Number(rounding) || 0
    updateItems((prev) => prev.map((row) => ({
      ...row,
      machiningStock: stockNum,
      roundingMm: roundNum,
      rmSize: computeRmSize(row.millingSize || row.size, stockNum, roundNum),
    })))
  }, [updateItems])

  const addMissingItem = useCallback(() => {
    updateItems((prev) => [
      ...prev,
      {
        id: `new-${Date.now()}`,
        name: 'New Part',
        partNumber: 'NEW-PART',
        instanceName: 'New Instance',
        description: 'New Description',
        material: '',
        manufacturer: '',
        catalogCode: '',
        remark: '',
        heatTreatment: 'NONE',
        sheetCategory: 'Steel',
        exportBucket: 'Steel',
        methodUsed: 'MANUAL',
        measurementConfidence: 'high',
        reviewStatus: 'needs_review',
        discrepancyType: 'extra',
        reviewNote: '',
        millingSize: '',
        size: '',
        rmSize: '',
        qty: 1,
        isStd: false,
        selected: true,
        keepInExport: true,
        validationFlags: ['manual_row'],
        includeIn2dDrawing: false,
      },
    ])
  }, [updateItems])

  const removeRow = useCallback((rowIndex) => {
    updateItems((prev) => prev.filter((_, i) => i !== rowIndex))
  }, [updateItems])

  const moveRowById = useCallback((fromRowId, toRowId) => {
    if (fromRowId == null || toRowId == null || String(fromRowId) === String(toRowId)) return
    updateItems((prev) => {
      const fromIndex = prev.findIndex((r) => String(r._rowId) === String(fromRowId))
      const toIndex = prev.findIndex((r) => String(r._rowId) === String(toRowId))
      if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return prev
      const next = [...prev]
      const [removed] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, removed)
      return next
    })
  }, [updateItems])

  const selectMfgFor2d = useCallback(() => {
    updateItems((prev) =>
      prev.map((row) => ({ ...row, includeIn2dDrawing: !row.isStd })),
    )
    setDraft2dFeedback('')
  }, [updateItems])

  const clear2dSelection = useCallback(() => {
    updateItems((prev) => prev.map((row) => ({ ...row, includeIn2dDrawing: false })))
    setDraft2dFeedback('')
  }, [updateItems])

  const apiErrorText = (data) => {
    if (data?.detail != null) {
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.detail)) {
        const first = data.detail[0]
        return first?.msg || first?.message || JSON.stringify(data.detail)
      }
    }
    return data?.error || 'Request failed'
  }

  const generate2dViews = useCallback(
    async (opts = {}) => {
      const useSelection = Boolean(opts.useSelection)
      const payloadItems = items.filter((row) => row.includeIn2dDrawing)
      if (!payloadItems.length) {
        setDraft2dFeedback('Select at least one row for 2D (use “Select MFG for 2D” or tick 2D).')
        return
      }
      setDraft2dLoading(true)
      setDraft2dFeedback('')
      try {
        const body = {
          items: payloadItems,
          globalDraftingAxisUseSelection: useSelection,
          topViewRotationDeg: -90,
          planProjectionUseLeft: true,
        }
        const trimmed = `${globalDraftingAxisName || ''}`.trim()
        if (!useSelection && trimmed) body.globalDraftingAxisName = trimmed
        const res = await fetch('/api/catia/drafting/multi-layout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        const data = await res.json()
        if (!res.ok) {
          setDraft2dFeedback(`2D layout failed: ${apiErrorText(data)}`)
          return
        }
        if (data.error) {
          setDraft2dFeedback(`2D layout failed: ${data.error}`)
          return
        }
        const w = (data.warnings || []).length ? ` Warnings: ${data.warnings.join('; ')}` : ''
        setDraft2dFeedback(
          `Opened drawing “${data.drawing_name || 'Drawing'}” — ${(data.views_created || []).length} view(s).${w}`,
        )
      } catch (err) {
        setDraft2dFeedback(`Request failed: ${err.message || err}`)
      } finally {
        setDraft2dLoading(false)
      }
    },
    [items, globalDraftingAxisName],
  )

  const previewDraftingAxis = useCallback(async (useSelection) => {
    setAxisPreviewLoading(true)
    setDraft2dFeedback('')
    setAxisPreviewOk(false)
    try {
      const body = useSelection ? { useSelection: true } : { name: `${globalDraftingAxisName || ''}`.trim() }
      if (!useSelection && !body.name) {
        setDraft2dFeedback('Type a drafting axis name, or use preview from selection.')
        return
      }
      const res = await fetch('/api/catia/drafting/axis-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setDraft2dFeedback(`Axis preview failed: ${apiErrorText(data)}`)
        return
      }
      if (!data.found) {
        setDraft2dFeedback('No matching axis found (check name or select an axis system in CATIA).')
        return
      }
      setAxisPreviewUsedSelection(useSelection)
      setAxisPreviewOk(true)
      setDraft2dFeedback(
        `Axis preview: “${data.name || '?'}”${data.catpartFullName ? ` — ${data.catpartFullName}` : ''}`,
      )
    } catch (err) {
      setDraft2dFeedback(`Axis preview failed: ${err.message || err}`)
    } finally {
      setAxisPreviewLoading(false)
    }
  }, [globalDraftingAxisName])

  const propagateAxisToMfgParts = useCallback(async () => {
    const payloadItems = items.filter((row) => row.includeIn2dDrawing)
    if (!payloadItems.length) {
      setDraft2dFeedback('Select at least one row for 2D (tick 2D) before propagating the axis.')
      return
    }
    setAxisPropagateLoading(true)
    setDraft2dFeedback('')
    try {
      const body = {
        items: payloadItems,
        globalDraftingAxisUseSelection: axisPreviewUsedSelection,
      }
      const trimmed = `${globalDraftingAxisName || ''}`.trim()
      if (!axisPreviewUsedSelection && trimmed) body.globalDraftingAxisName = trimmed
      const prev = await fetch('/api/catia/drafting/axis-propagate-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const prevData = await prev.json()
      if (!prev.ok) {
        setDraft2dFeedback(`Propagate preview failed: ${apiErrorText(prevData)}`)
        return
      }
      const cand = prevData.candidates || []
      const would = cand.filter((c) => c.action === 'would_create').length
      const summary = cand
        .map((c) => `${c.partKey}: ${c.action}${c.reason ? ` (${c.reason})` : ''}`)
        .join('\n')
      if (
        would > 0 &&
        !window.confirm(
          `Add axis “${prevData.propagatedAxisName || 'AXIS_DRAFTING_GLOBAL'}” to ${would} part(s)?`,
        )
      ) {
        setDraft2dFeedback('Propagate cancelled.')
        return
      }
      if (would === 0) {
        setDraft2dFeedback(
          `No parts need a new axis (all skipped or unresolved).\n${summary}`,
        )
        return
      }
      const exec = await fetch('/api/catia/drafting/axis-propagate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await exec.json()
      if (!exec.ok) {
        setDraft2dFeedback(`Propagate failed: ${apiErrorText(data)}`)
        return
      }
      const u = (data.updated || []).length
      const sk = (data.skipped || []).length
      const er = (data.errors || []).length
      const errLines = (data.errors || []).map((e) => `${e.partKey}: ${e.message}`).join('\n')
      setDraft2dFeedback(
        `Axis propagate: updated ${u}, skipped ${sk}, errors ${er}.${errLines ? `\n${errLines}` : ''}`,
      )
    } catch (err) {
      setDraft2dFeedback(`Propagate failed: ${err.message || err}`)
    } finally {
      setAxisPropagateLoading(false)
    }
  }, [items, globalDraftingAxisName, axisPreviewUsedSelection])

  const handleExport = useCallback(() => {
    const missingMaterialRows = items.filter(
      (row) => row.keepInExport && !row.isStd && ['Steel', 'Casting'].includes(row.sheetCategory) && !`${row.material || ''}`.trim()
    )
    if (missingMaterialRows.length) {
      setExportError(`Material is required for ${missingMaterialRows.length} Steel/Casting row(s) before export.`)
      return
    }
    const payload = items.map((row) => {
      const millingSize = row.millingSize || row.size
      const rmSize = computeRmSize(millingSize, row.machiningStock, row.roundingMm)
      return {
        ...row,
        millingSize,
        size: millingSize,
        rmSize,
        exportBucket: row.sheetCategory || row.exportBucket,
        validationFlags: normalizeFlags(row.validationFlags),
      }
    })
    setExportError('')
    onExport?.(payload)
  }, [items, onExport])

  const visibleRows = useMemo(() => {
    return items.filter((row) => {
      if (activeFilter === 'all') return true
      if (activeFilter === 'needs_review') return row.reviewStatus === 'needs_review' || normalizeFlags(row.validationFlags).length > 0
      if (activeFilter === 'approved') return row.reviewStatus === 'approved'
      return true
    })
  }, [activeFilter, items])

  const selectedItems = items.filter((row) => row.keepInExport)
  const mfgCount = selectedItems.filter((row) => !row.isStd).length
  const stdCount = selectedItems.filter((row) => row.isStd).length

  return (
    <div className={isFullscreen 
      ? "bom-editor h-full flex flex-col text-white antialiased" 
      : "bom-editor mt-4 rounded-xl border border-white/10 bg-black/40 overflow-hidden flex flex-col shadow-2xl backdrop-blur-md"}>
      
      {/* Top Toolbar - Modern Condensed */}
      <div className={`border-b border-white/10 flex flex-col ${isFullscreen ? 'bg-[#09090b]' : 'bg-white/5'}`}>
        <div className="flex items-center justify-between px-6 py-2 border-b border-white/5">
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <span className="text-[9px] font-bold text-blue-500 uppercase tracking-[0.2em]">BOM Engine</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/10 font-bold">MFG: {mfgCount}</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/10 font-bold">STD: {stdCount}</span>
              </div>
            </div>
            
            <div className="h-6 w-px bg-white/10"></div>

            {/* Filter Toggle Group */}
            <div className="flex bg-white/5 p-0.5 rounded-lg border border-white/10">
              {filterOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setActiveFilter(option.id)}
                  className={`text-[10px] px-3 py-1 rounded-md transition-all ${activeFilter === option.id ? 'bg-white text-black font-bold' : 'text-white/40 hover:text-white/70'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1">
              <button type="button" onClick={() => setAllSelected(true)} className="text-[10px] p-1.5 rounded-md hover:bg-white/5 text-white/40 hover:text-white transition-colors" title="Select All">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              </button>
              <button type="button" onClick={() => setAllSelected(false)} className="text-[10px] p-1.5 rounded-md hover:bg-white/5 text-white/40 hover:text-white transition-colors" title="Unselect All">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3">
             <button 
                onClick={() => setShowBulkActions(!showBulkActions)}
                className={`text-[10px] px-3 py-1.5 rounded-lg border transition-all flex items-center gap-2 ${showBulkActions ? 'bg-blue-600 text-white border-blue-500' : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10'}`}
             >
               <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
               Bulk Rules
             </button>

             <button 
                onClick={() => setIsCompactView(!isCompactView)}
                className={`text-[10px] px-3 py-1.5 rounded-lg border transition-all ${isCompactView ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/20' : 'bg-white/5 border-white/10 text-white/60'}`}
             >
               {isCompactView ? 'Compact View' : 'Comfortable View'}
             </button>

             <div className="h-6 w-px bg-white/10"></div>

             <button type="button" onClick={addMissingItem} className="text-[10px] px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-white/90">+ Row</button>
             
             <button type="button" onClick={handleExport} disabled={disabled} className="text-[10px] px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 font-bold shadow-lg shadow-blue-600/20">
               Export Excel
             </button>
          </div>
        </div>

        {/* Secondary Bulk Actions Toolbar (Collapsible) */}
        {showBulkActions && (
          <div className="px-6 py-2.5 bg-blue-600/5 flex items-center gap-4 animate-in slide-in-from-top duration-200">
            <span className="text-[9px] font-bold text-blue-400 uppercase tracking-widest">Global RM Stock Rules</span>
            <div className="flex items-center gap-2 bg-[#09090b] px-3 py-1 rounded-lg border border-blue-500/20">
              <span className="text-[9px] text-white/40 uppercase">Stock:</span>
              <input type="number" value={bulkStock} onChange={(e) => setBulkStock(e.target.value)} className="w-12 text-[11px] bg-transparent border-none focus:ring-0 p-0 text-blue-300" />
              <div className="w-px h-3 bg-white/10 mx-1"></div>
              <span className="text-[9px] text-white/40 uppercase">Round:</span>
              <input type="number" value={bulkRounding} onChange={(e) => setBulkRounding(e.target.value)} className="w-10 text-[11px] bg-transparent border-none focus:ring-0 p-0 text-blue-300" />
            </div>
            <button type="button" onClick={() => addMachiningStockToAll(bulkStock, bulkRounding)} className="text-[10px] px-4 py-1.5 rounded-lg bg-blue-600/20 text-blue-300 hover:bg-blue-600/40 border border-blue-500/20 transition-colors font-bold">Apply to All MFG</button>
            
            <div className="ml-auto flex items-center gap-2">
              <button 
                type="button" 
                onClick={() => setShowTechnicalColumns(!showTechnicalColumns)} 
                className={`text-[10px] px-3 py-1.5 rounded-lg border transition-all ${showTechnicalColumns ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'bg-white/5 border-white/10 text-white/60'}`}
              >
                {showTechnicalColumns ? 'Hide Tech Info' : 'Show Tech Info'}
              </button>
              <button 
                type="button" 
                onClick={() => setIsDraftingSidebarOpen(true)} 
                className="text-[10px] px-3 py-1.5 rounded-lg bg-sky-600/20 text-sky-300 border border-sky-500/20 hover:bg-sky-600/30 font-bold transition-all"
              >
                Drafting Assistant
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Drafting Sidebar */}
      {isDraftingSidebarOpen && (
        <>
          <div className="drafting-sidebar-backdrop animate-in fade-in transition-all duration-300" onClick={() => setIsDraftingSidebarOpen(false)}></div>
          <div className="drafting-sidebar p-6 flex flex-col gap-6 animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-widest text-sky-400">2D Drafting Tools</h3>
              <button 
                onClick={() => setIsDraftingSidebarOpen(false)}
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-sky-500/5 rounded-2xl border border-sky-500/10">
                <p className="text-[10px] text-sky-300 uppercase font-bold mb-3 tracking-wider">Bulk Selection</p>
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={selectMfgFor2d} className="text-[10px] px-3 py-2 rounded-xl bg-sky-500/20 text-sky-200 border border-sky-500/30 hover:bg-sky-500/30 transition-all font-semibold">
                    Select MFG
                  </button>
                  <button type="button" onClick={clear2dSelection} className="text-[10px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-white transition-all">
                    Clear All
                  </button>
                </div>
              </div>

              <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                <p className="text-[10px] text-white/40 uppercase font-bold mb-3 tracking-wider">Drafting Axis</p>
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Global axis name (e.g. DRAFTING_AXIS)"
                    value={globalDraftingAxisName}
                    onChange={(e) => setGlobalDraftingAxisName(e.target.value)}
                    className="w-full text-xs bg-white/5 border border-white/10 rounded-xl px-4 py-3 placeholder:text-white/20 focus:border-sky-500/50 transition-all outline-none"
                  />
                  <div className="grid grid-cols-1 gap-2">
                    <button
                      type="button"
                      onClick={() => previewDraftingAxis(false)}
                      disabled={disabled || axisPreviewLoading || draft2dLoading}
                      className="text-[11px] py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50 transition-all font-medium"
                    >
                      {axisPreviewLoading ? 'Searching…' : 'Preview By Name'}
                    </button>
                    <button
                      type="button"
                      onClick={() => previewDraftingAxis(true)}
                      disabled={disabled || axisPreviewLoading || draft2dLoading}
                      className="text-[11px] py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50 transition-all font-medium"
                    >
                      Preview Selection
                    </button>
                    <button
                      type="button"
                      onClick={propagateAxisToMfgParts}
                      disabled={disabled || !axisPreviewOk || axisPreviewLoading || axisPropagateLoading || draft2dLoading}
                      className="text-[11px] py-3 rounded-xl bg-violet-500 text-white hover:bg-violet-400 disabled:opacity-30 transition-all font-bold mt-2 shadow-lg shadow-violet-500/20"
                    >
                      {axisPropagateLoading ? 'Propagating…' : 'Apply Axis to All Parts'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-emerald-500/5 rounded-2xl border border-emerald-500/10">
                <p className="text-[10px] text-emerald-400 uppercase font-bold mb-3 tracking-wider">Generation</p>
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => generate2dViews()}
                    disabled={disabled || draft2dLoading}
                    className="w-full text-xs py-4 rounded-xl bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 transition-all font-bold shadow-lg shadow-emerald-600/20"
                  >
                    {draft2dLoading ? 'Generating Views…' : 'Generate 2D Layout'}
                  </button>
                  <button
                    type="button"
                    onClick={() => generate2dViews({ useSelection: true })}
                    disabled={disabled || draft2dLoading}
                    className="w-full text-[10px] py-2 rounded-xl bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 hover:bg-emerald-500/20 transition-all font-medium"
                  >
                    Quick Gen (Axis Selection)
                  </button>
                </div>
              </div>
            </div>
            
            <div className="mt-auto p-4 bg-white/5 rounded-xl">
              <p className="text-[10px] text-white/30 leading-relaxed italic">
                Tip: Ensure you have selected the correct parts in the "2D" column of the table before generating.
              </p>
            </div>
          </div>
        </>
      )}

      {exportError && (
        <div className="px-3 py-2 text-[11px] text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
          {exportError}
        </div>
      )}
      {draft2dFeedback && (
        <div className="px-3 py-2 text-[11px] text-emerald-200/90 bg-emerald-500/10 border-b border-emerald-500/20 whitespace-pre-wrap">
          {draft2dFeedback}
        </div>
      )}

      <div className={`overflow-x-auto overflow-y-auto ${isFullscreen ? 'flex-1 h-full' : 'max-h-[70vh]'}`}>
        <table className="w-full text-[11px] border-collapse min-w-max">
          <thead className="sticky top-0 bg-[#0d0d0e] z-40">
            <tr className="border-b border-white/10 bg-white/[0.02]">
              <th className="w-8 py-2 px-2 column-header"></th>
              <th className="w-8 py-2 px-1 column-header">IN</th>
              <th className="w-8 py-2 px-1 column-header">2D</th>
              <th className="w-32 py-2 px-3 text-left column-header">Qty</th>
              <th className="text-left py-2 px-4 min-w-[140px] column-header sticky-column sticky-left-instance bg-[#09090b]/80">Part Instance</th>
              <th className="text-left py-2 px-3 min-w-[140px] column-header">Excel Section</th>
              <th className="text-left py-2 px-3 min-w-[200px] column-header">Description</th>
              <th className="text-left py-2 px-3 min-w-[180px] column-header">Part / Catalog No</th>
              <th className="text-left py-2 px-3 min-w-[100px] column-header">Type / Category</th>
              <th className="text-left py-2 px-3 min-w-[140px] column-header">Manufacturer / Material</th>
              <th className="text-left py-2 px-3 min-w-[120px] column-header">Remark</th>
              <th className="text-left py-2 px-3 min-w-[110px] column-header">Review</th>
              
              {showTechnicalColumns && (
                <>
                  <th className="text-left py-2 px-3 min-w-[130px] column-header text-amber-400/60">Issue Type</th>
                  <th className="text-left py-2 px-3 min-w-[80px] column-header text-amber-400/60">Method</th>
                </>
              )}

              <th className="text-left py-2 px-3 min-w-[70px] column-header">L</th>
              <th className="text-left py-2 px-3 min-w-[70px] column-header">W</th>
              <th className="text-left py-2 px-3 min-w-[70px] column-header">H</th>
              <th className="text-left py-2 px-3 min-w-[70px] column-header">Stk</th>
              <th className="text-left py-2 px-3 min-w-[70px] column-header">Rnd</th>
              <th className="text-left py-2 px-4 min-w-[140px] column-header text-blue-400 font-bold">RM SIZE</th>

              {showTechnicalColumns && (
                <>
                  <th className="text-left py-4 px-3 w-20 column-header text-blue-400/60">RM L</th>
                  <th className="text-left py-4 px-3 w-20 column-header text-blue-400/60">RM W</th>
                  <th className="text-left py-4 px-3 w-20 column-header text-blue-400/60">RM H</th>
                  <th className="text-left py-4 px-3 min-w-[100px] column-header text-amber-400/60">Confidence</th>
                  <th className="text-left py-4 px-3 min-w-[180px] column-header text-amber-400/60">Flags / Notes</th>
                </>
              )}
              <th className="w-12 column-header" />
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const actualIndex = items.findIndex((candidate) => candidate._rowId === row._rowId)
              const rowKey = row._rowId ?? row.id ?? actualIndex
              const milling = parseSize(row.millingSize || row.size)
              const rm = parseSize(row.rmSize || computeRmSize(row.millingSize || row.size, row.machiningStock, row.roundingMm))
              const isStd = row.isStd
              const suggestions = getNameSuggestions(row)
              const datalistId = `editor-name-suggestions-${rowKey}`
              const materialRequired = !isStd && ['Steel', 'Casting'].includes(row.sheetCategory)
              const availableSheetOptions = isStd ? ['STD'] : ['Steel', 'MS', 'Casting']
              const isDragOver =
                draggingRowId != null &&
                dropTargetRowId != null &&
                String(dropTargetRowId) === String(rowKey) &&
                String(draggingRowId) !== String(rowKey)
              return (
                <tr
                  key={rowKey}
                  onDragOver={(e) => {
                    if (draggingRowId == null) return
                    e.preventDefault()
                    e.dataTransfer.dropEffect = 'move'
                    setDropTargetRowId(rowKey)
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    const fromId = e.dataTransfer.getData('text/plain')
                    if (fromId) moveRowById(fromId, rowKey)
                    setDraggingRowId(null)
                    setDropTargetRowId(null)
                  }}
                  className={`bom-table-row border-b border-white/[0.03] transition-colors group ${
                    draggingRowId != null && String(draggingRowId) === String(rowKey) ? 'opacity-30' : ''
                  } ${isDragOver ? 'bg-sky-500/15 ring-1 ring-inset ring-sky-400/40' : ''} ${isCompactView ? 'text-[11px]' : 'text-xs'}`}
                >
                  <td className="sticky-column sticky-left-handle py-1 px-1 align-middle bg-[#0d0d0e]/80 backdrop-blur-sm">
                    <span
                      role="button"
                      tabIndex={0}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(rowKey))
                        e.dataTransfer.effectAllowed = 'move'
                        setDraggingRowId(rowKey)
                      }}
                      onDragEnd={() => {
                        setDraggingRowId(null)
                        setDropTargetRowId(null)
                      }}
                      className="inline-flex cursor-grab active:cursor-grabbing text-white/5 group-hover:text-white/20 p-1 rounded-lg hover:bg-white/10 outline-none transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" /></svg>
                    </span>
                  </td>
                  <td className={`py-1 px-1 bg-[#0d0d0e]/80 backdrop-blur-sm text-center ${isCompactView ? 'w-6' : 'w-10'}`}>
                    <input type="checkbox" checked={row.keepInExport} onChange={(e) => updateRow(actualIndex, 'keepInExport', e.target.checked)} className="w-3.5 h-3.5 rounded border-white/10 bg-white/5 checked:bg-blue-500 transition-all cursor-pointer" />
                  </td>
                  <td className={`py-1 px-1 text-center ${isCompactView ? 'w-6' : 'w-10'}`}>
                    <input
                      type="checkbox"
                      checked={row.includeIn2dDrawing === true}
                      onChange={(e) => updateRow(actualIndex, 'includeIn2dDrawing', e.target.checked)}
                      className="w-3.5 h-3.5 rounded border-white/10 bg-white/5 checked:bg-emerald-500 transition-all cursor-pointer"
                    />
                  </td>
                  <td className="py-1 px-2">
                    <input type="number" min="1" value={row.qty || 1} onChange={(e) => updateRow(actualIndex, 'qty', e.target.value)} className={`w-14 bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-white/80`} />
                  </td>
                  <td className={`sticky-column sticky-left-instance py-1 px-4 bg-[#0d0d0e]/80 backdrop-blur-sm font-mono text-white/70 truncate max-w-[200px] ${isCompactView ? 'text-[9px]' : 'text-[10px]'}`} title={row.instanceName || row.name}>
                    {row.instanceName || row.name}
                  </td>
                  <td className="py-1 px-1">
                    <input
                      type="text"
                      value={row.parentAssembly || ''}
                      onChange={(e) => updateRow(actualIndex, 'parentAssembly', e.target.value)}
                      placeholder="—"
                      className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} font-mono placeholder:text-white/5 transition-all outline-none`}
                    />
                  </td>
                  <td className="py-1 px-1">
                    <input list={datalistId} type="text" value={row.description || ''} onChange={(e) => updateRow(actualIndex, 'description', e.target.value)} placeholder="Description" className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none`} />
                    <datalist id={datalistId}>
                      {suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
                    </datalist>
                  </td>
                  <td className="py-1 px-1">
                    <div className="flex flex-col gap-0.5">
                      <input type="text" value={row.partNumber || ''} onChange={(e) => updateRow(actualIndex, 'partNumber', e.target.value)} placeholder="Part No" className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none`} />
                      {isStd && (
                        <input type="text" value={row.catalogCode || ''} onChange={(e) => updateRow(actualIndex, 'catalogCode', e.target.value)} placeholder="Catalog" className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0 text-[8px]' : 'py-0.5 text-[9px]'} font-mono placeholder:text-white/10 transition-all outline-none`} />
                      )}
                    </div>
                  </td>
                  <td className="py-1 px-1">
                    <div className="flex flex-col gap-1">
                      <button
                        type="button"
                        onClick={() => updateRow(actualIndex, 'isStd', !isStd)}
                        className={`text-[8px] font-bold px-2 py-0.5 rounded-md border tracking-tighter transition-all ${isStd ? 'bg-amber-500/10 text-amber-400 border-amber-500/10' : 'bg-blue-500/10 text-blue-400 border-blue-500/10'}`}
                      >
                        {isStd ? 'STD' : 'MFG'}
                      </button>
                      <select value={row.sheetCategory || ''} onChange={(e) => updateRow(actualIndex, 'sheetCategory', e.target.value)} className="w-full bg-transparent border-transparent hover:border-white/10 focus:bg-white/5 text-[9px] px-1 py-0.5 outline-none cursor-pointer">
                        {availableSheetOptions.map((option) => <option key={option} value={option} className="bg-[#09090b]">{option}</option>)}
                      </select>
                    </div>
                  </td>
                  <td className="py-1 px-1">
                    <input
                      type="text"
                      value={isStd ? (row.manufacturer || '') : (row.material || '')}
                      onChange={(e) => updateRow(actualIndex, isStd ? 'manufacturer' : 'material', e.target.value)}
                      placeholder={isStd ? "Manufacturer" : "Material"}
                      className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} outline-none transition-all ${materialRequired && !`${row.material || ''}`.trim() ? 'bg-red-500/10 text-red-300' : ''}`}
                    />
                  </td>
                  <td className="py-1 px-1 text-center">
                    <input type="text" value={row.remark || ''} onChange={(e) => updateRow(actualIndex, 'remark', e.target.value)} placeholder="—" className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-2 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} transition-all outline-none`} />
                  </td>
                  <td className="py-1 px-1">
                    <select value={row.reviewStatus || 'needs_review'} onChange={(e) => updateRow(actualIndex, 'reviewStatus', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} outline-none cursor-pointer uppercase font-bold tracking-tighter ${row.reviewStatus === 'approved' ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {reviewOptions.map((option) => <option key={option} value={option} className="bg-[#09090b]">{option}</option>)}
                    </select>
                  </td>

                  {showTechnicalColumns && (
                    <>
                      <td className="py-1 px-1">
                        <select value={row.discrepancyType || ''} onChange={(e) => updateRow(actualIndex, 'discrepancyType', e.target.value)} className="w-full bg-transparent border-transparent hover:border-white/10 focus:bg-white/5 text-[9px] px-1 py-0.5 outline-none text-amber-200/50">
                          {discrepancyOptions.map((option) => <option key={option || 'none'} value={option} className="bg-[#09090b]">{option || 'none'}</option>)}
                        </select>
                      </td>
                      <td className="py-1 px-1 font-mono text-[9px] text-amber-200/30 uppercase text-center">{row.methodUsed || '—'}</td>
                    </>
                  )}

                  <td className="py-1 px-1"><input type="text" value={milling.l} onChange={(e) => updateMillingCell(actualIndex, 'l', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center`} /></td>
                  <td className="py-1 px-1"><input type="text" value={milling.w} onChange={(e) => updateMillingCell(actualIndex, 'w', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center`} /></td>
                  <td className="py-1 px-1"><input type="text" value={milling.h} onChange={(e) => updateMillingCell(actualIndex, 'h', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center`} /></td>
                  <td className="py-1 px-1"><input type="number" value={row.machiningStock || ''} onChange={(e) => updateRow(actualIndex, 'machiningStock', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-center text-white/40 hover:text-white`} /></td>
                  <td className="py-1 px-1"><input type="number" value={row.roundingMm || ''} onChange={(e) => updateRow(actualIndex, 'roundingMm', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-white/10 focus:border-blue-500/50 focus:bg-white/5 rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-center text-white/40 hover:text-white`} /></td>
                  
                  <td className={`py-1 px-4 font-mono font-bold bg-blue-500/5 text-blue-300 ${isCompactView ? 'text-[10px]' : 'text-xs'}`}>{row.rmSize || '—'}</td>

                  {showTechnicalColumns && (
                    <>
                      <td className={`py-1 px-1 font-mono text-blue-300/30 text-center ${isCompactView ? 'text-[8px]' : 'text-[9px]'}`}>{rm.l}</td>
                      <td className="py-3 px-2 font-mono text-[10px] text-blue-300/40">{rm.w}</td>
                      <td className="py-3 px-2 font-mono text-[10px] text-blue-300/40">{rm.h}</td>
                      <td className="py-3 px-2 text-[10px] text-amber-200/40 uppercase font-bold">{row.measurementConfidence || 'low'}</td>
                      <td className="py-3 px-2 text-[9px] text-amber-200/60 space-y-2">
                        <div className="font-bold">{normalizeFlags(row.validationFlags).length ? normalizeFlags(row.validationFlags).join(', ') : 'VALIDATED'}</div>
                        <input type="text" value={row.reviewNote || ''} onChange={(e) => updateRow(actualIndex, 'reviewNote', e.target.value)} placeholder="Audit note..." className="w-full min-w-[160px] text-[10px] bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white/50 focus:border-blue-500/50 outline-none" />
                      </td>
                    </>
                  )}
                  
                  <td className="py-3 px-2">
                    {row.id?.toString().startsWith('new-') && (
                      <button type="button" onClick={() => removeRow(actualIndex)} className="p-2 hover:bg-red-500/10 text-red-400/50 hover:text-red-400 transition-all rounded-full" title="Remove Row">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                      </button>
                    )}
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

export { computeRmSize, parseSize }
