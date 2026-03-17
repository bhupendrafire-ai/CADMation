import { useState, useEffect, useRef } from 'react'
import { startBomMeasurement } from '../utils/bomMeasurement'
import { getNameSuggestions } from '../utils/bomNaming'

const DEFAULT_METHOD = 'ROUGH_STOCK'

function normalizeRows(items) {
  return (items || []).map((item) => {
    const incomingCategory = item.sheetCategory || ''
    const isStd = item.isStd || incomingCategory.startsWith('STD')
    const sheetCategory = isStd ? 'STD' : (incomingCategory && ['Steel', 'MS', 'Casting'].includes(incomingCategory) ? incomingCategory : 'Steel')
    return {
      ...item,
      selected: item.selected !== false,
      isStd,
      sheetCategory,
      manufacturer: item.manufacturer || (isStd ? 'MISUMI' : ''),
      description: item.description || getNameSuggestions(item)[0] || item.instanceName || item.name,
      material: item.material || '',
    }
  })
}

export default function BOMSelectionList({ items: initialItems, onCalculationComplete }) {
  const [items, setItems] = useState(() => normalizeRows(initialItems))
  const [calculating, setCalculating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [logs, setLogs] = useState([])
  const [selectorError, setSelectorError] = useState('')
  const wsRef = useRef(null)
  const logEndRef = useRef(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    setItems(normalizeRows(initialItems))
  }, [initialItems])

  useEffect(() => {
    if (calculating && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, calculating])

  const updateItem = (id, updater) => {
    setItems((prev) => prev.map((item) => (item.id === id ? updater(item) : item)))
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

  const validateBeforeMeasurement = (selectedItems) => {
    const missingMaterialRows = selectedItems.filter((item) => !item.isStd && ['Steel', 'Casting'].includes(item.sheetCategory) && !`${item.material || ''}`.trim())
    if (missingMaterialRows.length) {
      return `Material is required for ${missingMaterialRows.length} Steel/Casting row(s) before measurement.`
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

    setCalculating(true)
    setProgress(0)
    setLogs(['Connecting to measure engine...'])
    setSelectorError('')
    cancelledRef.current = false

    const ws = startBomMeasurement({
      items: selectedItems,
      method: DEFAULT_METHOD,
      onOpen: () => {
        setLogs((prev) => [...prev, 'Starting measurement process (Rough Stock default)...'])
      },
      onProgress: (nextProgress) => {
        if (!cancelledRef.current) setProgress(nextProgress)
      },
      onLog: (log) => {
        if (!cancelledRef.current) setLogs((prev) => [...prev, log])
      },
      onDone: (data) => {
        if (cancelledRef.current) return
        setLogs((prev) => [...prev, 'Done! Finalizing results...'])
        setTimeout(() => {
          onCalculationComplete?.({
            results: data.results,
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

  if (calculating) {
    return (
      <div className="mt-4 p-4 rounded-xl border border-white/10 bg-black/40 space-y-4">
        <div className="flex items-center justify-between text-xs font-medium text-white/50 mb-1 gap-2">
          <span className="truncate max-w-[60%]">{logs[logs.length - 1]}</span>
          <span className="shrink-0">{progress}%</span>
          <button
            type="button"
            onClick={cancelCalculation}
            className="shrink-0 text-[10px] font-bold px-2 py-1 rounded bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition-colors"
          >
            Cancel
          </button>
        </div>
        <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full bg-white transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
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
            Choose MFG/STD, route MFG rows into Steel/MS/Casting, rename parts, and enter material for Steel/Casting.
          </span>
        </div>
        <div className="flex gap-2">
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

      <div className="overflow-x-auto max-h-[55vh] overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-black/50 z-10">
            <tr className="border-b border-white/10">
              <th className="text-left py-2 px-2 w-8">In</th>
              <th className="text-left py-2 px-2 min-w-[150px]">Instance</th>
              <th className="text-left py-2 px-2 min-w-[180px]">Rename / Description</th>
              <th className="text-left py-2 px-2 min-w-[100px]">Type</th>
              <th className="text-left py-2 px-2 min-w-[110px]">Sheet</th>
              <th className="text-left py-2 px-2 min-w-[120px]">Material / Vendor</th>
              <th className="text-left py-2 px-2 w-16">Qty</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const suggestions = getNameSuggestions(item)
              const datalistId = `bom-name-suggestions-${idx}`
              const classification = item.isStd ? 'STD' : 'MFG'
              const categoryOptions = item.isStd ? ['STD'] : ['Steel', 'MS', 'Casting']
              return (
                <tr key={`${item.id}-${idx}`} className={`border-b border-white/5 ${item.selected ? 'bg-white/[0.03]' : ''}`}>
                  <td className="py-2 px-2">
                    <input type="checkbox" checked={item.selected} onChange={() => toggleItem(item.id)} className="rounded border-white/20" />
                  </td>
                  <td className="py-2 px-2">
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-semibold truncate text-white/90">{item.instanceName}</span>
                      <span className="text-[10px] font-mono opacity-50 truncate">{item.name}</span>
                    </div>
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
                      placeholder={item.isStd ? 'MISUMI / Vendor' : 'Required for Steel/Casting'}
                      className={`w-full min-w-[120px] text-[11px] border rounded px-2 py-1 ${!item.isStd && ['Steel', 'Casting'].includes(item.sheetCategory) && !`${item.material || ''}`.trim() ? 'bg-red-500/10 border-red-500/30' : 'bg-white/5 border-white/10'}`}
                    />
                  </td>
                  <td className="py-2 px-2 text-white/60">{item.qty || 1}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="p-3 border-t border-white/10 flex justify-end">
        <button
          onClick={startCalculation}
          className="bg-white text-black text-xs font-bold px-4 py-2 rounded-lg hover:bg-neutral-200 transition-all active:scale-95 flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          Calculate Dimensions
        </button>
      </div>
    </div>
  )
}
