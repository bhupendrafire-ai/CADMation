import { useState, useCallback } from 'react'

/**
 * Parses "L x W x H" (mm) and returns [L, W, H] or null.
 */
function parseSize(sizeStr) {
  if (!sizeStr || typeof sizeStr !== 'string') return null
  const parts = sizeStr.split(/\s*x\s*/i).map((s) => parseFloat(s.trim()))
  if (parts.length >= 3 && parts.every((n) => !Number.isNaN(n))) return parts
  return null
}

/**
 * Computes RM Size: add machining stock to each dimension, round to nearest rounding step.
 */
function computeRmSize(sizeStr, machiningStock = 0, roundingMm = 0) {
  const dims = parseSize(sizeStr)
  if (!dims) return sizeStr || '—'
  const add = Number(machiningStock) || 0
  const step = Number(roundingMm) || 1
  const rounded = dims.map((d) => (step > 0 ? Math.round((d + add) / step) * step : d + add))
  return rounded.join(' x ')
}

export default function BOMEditor({ items: initialItems, onItemsChange, onExport, disabled }) {
  const normalize = (list) =>
    (list || []).map((row, i) => ({
      ...row,
      selected: row.selected !== false,
      isStd: row.isStd || false,
      machiningStock: Number(row.machiningStock) || 0,
      roundingMm: Number(row.roundingMm) || 0,
      _rowId: row.id ?? i + 1,
    }))

  const [items, setItems] = useState(() => normalize(initialItems))

  const updateRow = useCallback((rowIndex, field, value) => {
    setItems((prev) => {
      const next = prev.map((r, i) =>
        i === rowIndex ? { ...r, [field]: value } : r
      )
      onItemsChange?.(next)
      return next
    })
  }, [onItemsChange])

  const setAllSelected = useCallback((selected) => {
    setItems((prev) => {
      const next = prev.map((r) => ({ ...r, selected }))
      onItemsChange?.(next)
      return next
    })
  }, [onItemsChange])

  const addMachiningStockToAll = useCallback((stock, rounding) => {
    const stockNum = Number(stock) || 0
    const roundNum = Number(rounding) || 0
    setItems((prev) => {
      const next = prev.map((r) => ({
        ...r,
        machiningStock: stockNum,
        roundingMm: roundNum,
      }))
      onItemsChange?.(next)
      return next
    })
  }, [onItemsChange])

  const addMissingItem = useCallback(() => {
    const newItem = {
      id: `new-${Date.now()}`,
      _rowId: items.length + 1,
      name: 'New Instance',
      partNumber: 'New Part',
      instanceName: 'New Instance',
      material: 'STEEL',
      size: '',
      heatTreatment: 'NONE',
      qty: 1,
      isStd: false,
      manufacturer: '',
      selected: true,
      machiningStock: 0,
      roundingMm: 0,
    }
    setItems((prev) => {
      const next = [...prev, newItem]
      onItemsChange?.(next)
      return next
    })
  }, [items.length, onItemsChange])

  const removeRow = useCallback((rowIndex) => {
    setItems((prev) => {
      const next = prev.filter((_, i) => i !== rowIndex)
      onItemsChange?.(next)
      return next
    })
  }, [onItemsChange])

  const handleExport = useCallback(() => {
    const payload = items.map((r) => ({
      ...r,
      rmSize: computeRmSize(r.size, r.machiningStock, r.roundingMm),
    }))
    onExport?.(payload)
  }, [items, onExport])

  const [bulkStock, setBulkStock] = useState('')
  const [bulkRounding, setBulkRounding] = useState('5')

  // Counts for the summary bar
  const mfgCount = items.filter((r) => r.selected && !r.isStd).length
  const stdCount = items.filter((r) => r.selected && r.isStd).length

  return (
    <div className="bom-editor mt-4 rounded-lg border border-white/10 bg-black/20 overflow-hidden">
      <div className="p-3 border-b border-white/10 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          BOM — Select items and set sizes
        </span>

        {/* MFG/STD count badges */}
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
          MFG: {mfgCount}
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
          STD: {stdCount}
        </span>

        <button
          type="button"
          onClick={() => setAllSelected(true)}
          className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20"
        >
          Select all
        </button>
        <button
          type="button"
          onClick={() => setAllSelected(false)}
          className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20"
        >
          Unselect all
        </button>
        <div className="flex items-center gap-1">
          <input
            type="number"
            placeholder="Stock (mm)"
            value={bulkStock}
            onChange={(e) => setBulkStock(e.target.value)}
            className="w-20 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
          />
          <input
            type="number"
            placeholder="Round"
            value={bulkRounding}
            onChange={(e) => setBulkRounding(e.target.value)}
            className="w-16 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
          />
          <button
            type="button"
            onClick={() => addMachiningStockToAll(bulkStock, bulkRounding)}
            className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20"
          >
            Apply to all
          </button>
        </div>
        <button
          type="button"
          onClick={addMissingItem}
          className="text-[10px] px-2 py-1 rounded bg-white/10 hover:bg-white/20"
        >
          + Add missing item
        </button>
        <button
          type="button"
          onClick={handleExport}
          disabled={disabled}
          className="text-[10px] px-3 py-1 rounded bg-white text-black hover:bg-neutral-200 disabled:opacity-50 ml-auto"
        >
          Export to Excel
        </button>
      </div>

      <div className="overflow-x-auto max-h-[60vh] overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-black/40 z-10">
            <tr className="border-b border-white/10">
              <th className="text-left py-2 px-2 w-8">Include</th>
              <th className="text-left py-2 px-2 min-w-[140px]">Instance Name</th>
              <th className="text-left py-2 px-2 min-w-[120px]">Part Number</th>
              <th className="text-left py-2 px-2 w-20">Type</th>
              <th className="text-left py-2 px-2 min-w-[120px]">Size (mm)</th>
              <th className="text-left py-2 px-2 min-w-[90px]">Heat treatment</th>
              <th className="text-left py-2 px-2 w-16">Stock (mm)</th>
              <th className="text-left py-2 px-2 w-14">Round</th>
              <th className="text-left py-2 px-2 min-w-[110px]">RM Size</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {items.map((row, i) => (
              <tr
                key={row._rowId ?? row.id ?? i}
                className="border-b border-white/5 hover:bg-white/5"
              >
                <td className="py-1 px-2">
                  <input
                    type="checkbox"
                    checked={row.selected}
                    onChange={(e) => updateRow(i, 'selected', e.target.checked)}
                    className="rounded border-white/20"
                  />
                </td>
                <td className="py-1 px-2 font-mono truncate max-w-[180px]" title={row.instanceName || row.name}>
                  {row.instanceName || row.name}
                </td>
                <td className="py-1 px-2 font-mono truncate max-w-[150px]" title={row.partNumber}>
                  {row.partNumber}
                </td>

                {/* STD / MFG toggle button — switches classification on click */}
                <td className="py-1 px-2">
                  <button
                    type="button"
                    onClick={() => updateRow(i, 'isStd', !row.isStd)}
                    title={row.isStd ? 'Standard part (click to set MFG)' : 'Manufactured part (click to set STD)'}
                    className={`
                      text-[10px] font-bold px-2 py-0.5 rounded-full border transition-colors cursor-pointer
                      ${row.isStd
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300 border-blue-500/40 hover:bg-blue-500/30'
                      }
                    `}
                  >
                    {row.isStd ? 'STD' : 'MFG'}
                  </button>
                </td>

                <td className="py-1 px-2">
                  <input
                    type="text"
                    value={row.size}
                    onChange={(e) => updateRow(i, 'size', e.target.value)}
                    placeholder="L x W x H"
                    className="w-full min-w-[100px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1 font-mono"
                  />
                </td>
                <td className="py-1 px-2">
                  <input
                    type="text"
                    value={row.heatTreatment}
                    onChange={(e) => updateRow(i, 'heatTreatment', e.target.value)}
                    className="w-full min-w-[70px] text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
                  />
                </td>
                <td className="py-1 px-2">
                  <input
                    type="number"
                    value={row.machiningStock || ''}
                    onChange={(e) => updateRow(i, 'machiningStock', e.target.value)}
                    className="w-14 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
                  />
                </td>
                <td className="py-1 px-2">
                  <input
                    type="number"
                    value={row.roundingMm || ''}
                    onChange={(e) => updateRow(i, 'roundingMm', e.target.value)}
                    placeholder="5"
                    className="w-12 text-[11px] bg-white/5 border border-white/10 rounded px-2 py-1"
                  />
                </td>
                <td className="py-1 px-2 font-mono text-muted-foreground">
                  {computeRmSize(row.size, row.machiningStock, row.roundingMm)}
                </td>
                <td className="py-1 px-1">
                  {row.id?.toString().startsWith('new-') && (
                    <button
                      type="button"
                      onClick={() => removeRow(i)}
                      className="text-red-400/80 hover:text-red-400 text-[10px]"
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export { computeRmSize, parseSize }
