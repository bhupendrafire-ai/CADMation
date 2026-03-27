import { useState, useCallback, useEffect, useMemo } from 'react'
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

export default function BOMEditor({ items: initialItems, onItemsChange, onExport, disabled }) {
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

  useEffect(() => {
    setItems(normalizeRows(initialItems))
  }, [initialItems])

  useEffect(() => {
    setAxisPreviewOk(false)
  }, [globalDraftingAxisName])

  const updateItems = useCallback((updater) => {
    setItems((prev) => {
      const next = normalizeRows(typeof updater === 'function' ? updater(prev) : updater)
      setExportError('')
      onItemsChange?.(next)
      return next
    })
  }, [onItemsChange])

  const updateRow = useCallback((rowIndex, field, value) => {
    updateItems((prev) => prev.map((row, i) => {
      if (i !== rowIndex) return row
      const next = { ...row, [field]: value }
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
    <div className="bom-editor mt-4 rounded-lg border border-white/10 bg-black/20 overflow-hidden">
      <div className="p-3 border-b border-white/10 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          BOM review draft
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">MFG: {mfgCount}</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">STD: {stdCount}</span>
        {filterOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setActiveFilter(option.id)}
            className={`text-[10px] px-2 py-1 rounded border ${activeFilter === option.id ? 'bg-white text-black border-white' : 'bg-white/5 border-white/10 hover:bg-white/10'}`}
          >
            {option.label}
          </button>
        ))}
        <button type="button" onClick={() => setAllSelected(true)} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">Select all</button>
        <button type="button" onClick={() => setAllSelected(false)} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">Unselect all</button>
        <span className="text-white/15 hidden sm:inline">|</span>
        <button type="button" onClick={selectMfgFor2d} className="text-[10px] px-2 py-1 rounded bg-sky-500/15 text-sky-200 border border-sky-500/30 hover:bg-sky-500/25">
          Select MFG for 2D
        </button>
        <button type="button" onClick={clear2dSelection} className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10">
          Clear 2D
        </button>
        <input
          type="text"
          placeholder="Global drafting axis (name)"
          value={globalDraftingAxisName}
          onChange={(e) => setGlobalDraftingAxisName(e.target.value)}
          title="Optional: substring to match one Part Axis System for all rows. Leave empty for per-row drafting axis only."
          className="min-w-[120px] max-w-[190px] text-[10px] bg-white/5 border border-white/10 rounded px-2 py-1 placeholder:text-white/35"
        />
        <button
          type="button"
          onClick={() => previewDraftingAxis(false)}
          disabled={disabled || axisPreviewLoading || draft2dLoading}
          className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50"
        >
          {axisPreviewLoading ? '…' : 'Preview axis'}
        </button>
        <button
          type="button"
          onClick={() => previewDraftingAxis(true)}
          disabled={disabled || axisPreviewLoading || draft2dLoading}
          className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50"
          title="Resolve axis from current CATIA selection (pick axis in the spec tree first)"
        >
          Preview selection
        </button>
        <button
          type="button"
          onClick={propagateAxisToMfgParts}
          disabled={disabled || !axisPreviewOk || axisPreviewLoading || axisPropagateLoading || draft2dLoading}
          className="text-[10px] px-2 py-1 rounded bg-violet-500/20 text-violet-100 border border-violet-500/35 hover:bg-violet-500/30 disabled:opacity-50"
          title="After a successful axis preview, create AXIS_DRAFTING_GLOBAL in CATParts that lack a usable axis (2D rows)"
        >
          {axisPropagateLoading ? '…' : 'Propagate axis to MFG parts'}
        </button>
        <button
          type="button"
          onClick={() => generate2dViews()}
          disabled={disabled || draft2dLoading}
          className="text-[10px] px-2 py-1 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-500/35 hover:bg-emerald-500/30 disabled:opacity-50"
        >
          {draft2dLoading ? 'Generating…' : 'Generate 2D views'}
        </button>
        <button
          type="button"
          onClick={() => generate2dViews({ useSelection: true })}
          disabled={disabled || draft2dLoading}
          className="text-[10px] px-2 py-1 rounded bg-emerald-500/15 text-emerald-100/90 border border-emerald-500/25 hover:bg-emerald-500/25 disabled:opacity-50"
          title="Use the axis system currently selected in CATIA for all parts (DefineFrontView); SetAxisSysteme only if that axis lives in the same CATPart as the row"
        >
          {draft2dLoading ? 'Generating…' : 'Generate 2D (axis from selection)'}
        </button>
        <div className="flex items-center gap-1">
          <input type="number" placeholder="Stock (mm)" value={bulkStock} onChange={(e) => setBulkStock(e.target.value)} className="w-20 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
          <input type="number" placeholder="Round" value={bulkRounding} onChange={(e) => setBulkRounding(e.target.value)} className="w-16 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
          <button type="button" onClick={() => addMachiningStockToAll(bulkStock, bulkRounding)} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">Apply RM rules</button>
        </div>
        <button type="button" onClick={addMissingItem} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">+ Add row</button>
        <span className="text-[10px] text-muted-foreground hidden md:inline">
          Drag ⋮⋮ to reorder. Use Section for Excel group headers (e.g. LOWER NON STD PARTS).
        </span>
        <button type="button" onClick={handleExport} disabled={disabled} className="text-[10px] px-3 py-1 rounded bg-white text-black hover:bg-neutral-200 disabled:opacity-50 ml-auto">
          Export to Excel
        </button>
      </div>

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

      <div className="overflow-x-auto max-h-[65vh] overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-black/50 z-10">
            <tr className="border-b border-white/10">
              <th className="text-left py-2 px-1 w-7" title="Drag to reorder"> </th>
              <th className="text-left py-2 px-2 w-8">In</th>
              <th className="text-left py-2 px-2 w-8" title="Include in multi-part 2D layout">
                2D
              </th>
              <th className="text-left py-2 px-2 w-14">Qty</th>
              <th className="text-left py-2 px-2 min-w-[150px]">Instance</th>
              <th className="text-left py-2 px-2 min-w-[130px]">Section</th>
              <th className="text-left py-2 px-2 min-w-[180px]">Description</th>
              <th className="text-left py-2 px-2 min-w-[150px]">Part / Catalog</th>
              <th className="text-left py-2 px-2 min-w-[100px]">Sheet</th>
              <th className="text-left py-2 px-2 min-w-[110px]">Material / Vendor</th>
              <th className="text-left py-2 px-2 min-w-[100px]">Remark</th>
              <th className="text-left py-2 px-2 min-w-[90px]">Review</th>
              <th className="text-left py-2 px-2 min-w-[100px]">Issue</th>
              <th className="text-left py-2 px-2 min-w-[80px]">Method</th>
              <th className="text-left py-2 px-2 w-20">L</th>
              <th className="text-left py-2 px-2 w-20">W</th>
              <th className="text-left py-2 px-2 w-20">H</th>
              <th className="text-left py-2 px-2 w-16">Stock</th>
              <th className="text-left py-2 px-2 w-16">Round</th>
              <th className="text-left py-2 px-2 w-20">RM L</th>
              <th className="text-left py-2 px-2 w-20">RM W</th>
              <th className="text-left py-2 px-2 w-20">RM H</th>
              <th className="text-left py-2 px-2 min-w-[90px]">Confidence</th>
              <th className="text-left py-2 px-2 min-w-[160px]">Flags / Notes</th>
              <th className="w-8" />
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
                  className={`border-b border-white/5 hover:bg-white/5 align-top transition-colors ${
                    draggingRowId != null && String(draggingRowId) === String(rowKey) ? 'opacity-50' : ''
                  } ${isDragOver ? 'bg-sky-500/15 ring-1 ring-inset ring-sky-400/40' : ''}`}
                >
                  <td className="py-1 px-1 align-middle w-7">
                    <span
                      role="button"
                      tabIndex={0}
                      draggable
                      title="Drag to reorder"
                      aria-label="Drag row to reorder"
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(rowKey))
                        e.dataTransfer.effectAllowed = 'move'
                        setDraggingRowId(rowKey)
                      }}
                      onDragEnd={() => {
                        setDraggingRowId(null)
                        setDropTargetRowId(null)
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
                  <td className="py-1 px-2">
                    <input type="checkbox" checked={row.keepInExport} onChange={(e) => updateRow(actualIndex, 'keepInExport', e.target.checked)} className="rounded border-white/20" />
                  </td>
                  <td className="py-1 px-2">
                    <input
                      type="checkbox"
                      checked={row.includeIn2dDrawing === true}
                      onChange={(e) => updateRow(actualIndex, 'includeIn2dDrawing', e.target.checked)}
                      className="rounded border-white/20"
                      title="Add to CATDrawing multi-layout (Front / Top)"
                    />
                  </td>
                  <td className="py-1 px-2">
                    <input type="number" min="1" value={row.qty || 1} onChange={(e) => updateRow(actualIndex, 'qty', e.target.value)} className="w-12 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
                  </td>
                  <td className="py-1 px-2 font-mono truncate max-w-[180px]" title={row.instanceName || row.name}>{row.instanceName || row.name}</td>
                  <td className="py-1 px-2">
                    <input
                      type="text"
                      value={row.parentAssembly || ''}
                      onChange={(e) => updateRow(actualIndex, 'parentAssembly', e.target.value)}
                      placeholder="LOWER NON STD PARTS"
                      title="Excel section header; group rows with the same value"
                      className="w-full min-w-[120px] text-[10px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono placeholder:text-white/25"
                    />
                  </td>
                  <td className="py-1 px-2">
                    <input list={datalistId} type="text" value={row.description || ''} onChange={(e) => updateRow(actualIndex, 'description', e.target.value)} className="w-full min-w-[160px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
                    <datalist id={datalistId}>
                      {suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
                    </datalist>
                  </td>
                  <td className="py-1 px-2 space-y-1">
                    <input type="text" value={row.partNumber || ''} onChange={(e) => updateRow(actualIndex, 'partNumber', e.target.value)} className="w-full min-w-[140px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono" />
                    {isStd && (
                      <input type="text" value={row.catalogCode || ''} onChange={(e) => updateRow(actualIndex, 'catalogCode', e.target.value)} placeholder="Catalog code" className="w-full min-w-[140px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono" />
                    )}
                  </td>
                  <td className="py-1 px-2 space-y-1">
                    <button
                      type="button"
                      onClick={() => updateRow(actualIndex, 'isStd', !isStd)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border transition-colors ${isStd ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30' : 'bg-blue-500/20 text-blue-300 border-blue-500/40 hover:bg-blue-500/30'}`}
                    >
                      {isStd ? 'STD' : 'MFG'}
                    </button>
                    <select value={row.sheetCategory || ''} onChange={(e) => updateRow(actualIndex, 'sheetCategory', e.target.value)} className="w-full min-w-[92px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1">
                      {availableSheetOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  </td>
                  <td className="py-1 px-2">
                    <input
                      type="text"
                      value={isStd ? (row.manufacturer || '') : (row.material || '')}
                      onChange={(e) => updateRow(actualIndex, isStd ? 'manufacturer' : 'material', e.target.value)}
                      className={`w-full min-w-[100px] text-[11px] border rounded px-2 py-1 ${materialRequired && !`${row.material || ''}`.trim() ? 'bg-red-500/10 border-red-500/30' : 'bg-white/5 border-white/10'}`}
                    />
                  </td>
                  <td className="py-1 px-2">
                    <input type="text" value={row.remark || ''} onChange={(e) => updateRow(actualIndex, 'remark', e.target.value)} className="w-full min-w-[90px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
                  </td>
                  <td className="py-1 px-2">
                    <select value={row.reviewStatus || 'needs_review'} onChange={(e) => updateRow(actualIndex, 'reviewStatus', e.target.value)} className="w-full min-w-[92px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1">
                      {reviewOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  </td>
                  <td className="py-1 px-2">
                    <select value={row.discrepancyType || ''} onChange={(e) => updateRow(actualIndex, 'discrepancyType', e.target.value)} className="w-full min-w-[92px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1">
                      {discrepancyOptions.map((option) => <option key={option || 'none'} value={option}>{option || 'none'}</option>)}
                    </select>
                  </td>
                  <td className="py-1 px-2 font-mono text-white/70">{row.methodUsed || 'UNKNOWN'}</td>
                  <td className="py-1 px-2"><input type="text" value={milling.l} onChange={(e) => updateMillingCell(actualIndex, 'l', e.target.value)} className="w-full min-w-[64px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono" /></td>
                  <td className="py-1 px-2"><input type="text" value={milling.w} onChange={(e) => updateMillingCell(actualIndex, 'w', e.target.value)} className="w-full min-w-[64px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono" /></td>
                  <td className="py-1 px-2"><input type="text" value={milling.h} onChange={(e) => updateMillingCell(actualIndex, 'h', e.target.value)} className="w-full min-w-[64px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono" /></td>
                  <td className="py-1 px-2"><input type="number" value={row.machiningStock || ''} onChange={(e) => updateRow(actualIndex, 'machiningStock', e.target.value)} className="w-14 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" /></td>
                  <td className="py-1 px-2"><input type="number" value={row.roundingMm || ''} onChange={(e) => updateRow(actualIndex, 'roundingMm', e.target.value)} className="w-14 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" /></td>
                  <td className="py-1 px-2 font-mono text-muted-foreground">{rm.l}</td>
                  <td className="py-1 px-2 font-mono text-muted-foreground">{rm.w}</td>
                  <td className="py-1 px-2 font-mono text-muted-foreground">{rm.h}</td>
                  <td className="py-1 px-2 text-[10px] text-white/60 uppercase">{row.measurementConfidence || 'low'}</td>
                  <td className="py-1 px-2 text-[10px] text-amber-200/80 space-y-1">
                    <div>{normalizeFlags(row.validationFlags).length ? normalizeFlags(row.validationFlags).join(', ') : 'OK'}</div>
                    <input type="text" value={row.reviewNote || ''} onChange={(e) => updateRow(actualIndex, 'reviewNote', e.target.value)} placeholder="Review note" className="w-full min-w-[140px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 text-white/70" />
                  </td>
                  <td className="py-1 px-1">
                    {row.id?.toString().startsWith('new-') && (
                      <button type="button" onClick={() => removeRow(actualIndex)} className="text-red-400/80 hover:text-red-400 text-[10px]">
                        Remove
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
