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

  useEffect(() => {
    setItems(normalizeRows(initialItems))
  }, [initialItems])

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
      },
    ])
  }, [updateItems])

  const removeRow = useCallback((rowIndex) => {
    updateItems((prev) => prev.filter((_, i) => i !== rowIndex))
  }, [updateItems])

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
        <div className="flex items-center gap-1">
          <input type="number" placeholder="Stock (mm)" value={bulkStock} onChange={(e) => setBulkStock(e.target.value)} className="w-20 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
          <input type="number" placeholder="Round" value={bulkRounding} onChange={(e) => setBulkRounding(e.target.value)} className="w-16 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
          <button type="button" onClick={() => addMachiningStockToAll(bulkStock, bulkRounding)} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">Apply RM rules</button>
        </div>
        <button type="button" onClick={addMissingItem} className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">+ Add row</button>
        <button type="button" onClick={handleExport} disabled={disabled} className="text-[10px] px-3 py-1 rounded bg-white text-black hover:bg-neutral-200 disabled:opacity-50 ml-auto">
          Export to Excel
        </button>
      </div>

      {exportError && (
        <div className="px-3 py-2 text-[11px] text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
          {exportError}
        </div>
      )}

      <div className="overflow-x-auto max-h-[65vh] overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-black/50 z-10">
            <tr className="border-b border-white/10">
              <th className="text-left py-2 px-2 w-8">In</th>
              <th className="text-left py-2 px-2 w-14">Qty</th>
              <th className="text-left py-2 px-2 min-w-[150px]">Instance</th>
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
              const milling = parseSize(row.millingSize || row.size)
              const rm = parseSize(row.rmSize || computeRmSize(row.millingSize || row.size, row.machiningStock, row.roundingMm))
              const isStd = row.isStd
              const suggestions = getNameSuggestions(row)
              const datalistId = `editor-name-suggestions-${row._rowId ?? actualIndex}`
              const materialRequired = !isStd && ['Steel', 'Casting'].includes(row.sheetCategory)
              const availableSheetOptions = isStd ? ['STD'] : ['Steel', 'MS', 'Casting']
              return (
                <tr key={row._rowId ?? row.id ?? actualIndex} className="border-b border-white/5 hover:bg-white/5 align-top">
                  <td className="py-1 px-2">
                    <input type="checkbox" checked={row.keepInExport} onChange={(e) => updateRow(actualIndex, 'keepInExport', e.target.checked)} className="rounded border-white/20" />
                  </td>
                  <td className="py-1 px-2">
                    <input type="number" min="1" value={row.qty || 1} onChange={(e) => updateRow(actualIndex, 'qty', e.target.value)} className="w-12 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1" />
                  </td>
                  <td className="py-1 px-2 font-mono truncate max-w-[180px]" title={row.instanceName || row.name}>{row.instanceName || row.name}</td>
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
