import { useState, useMemo, useEffect, useRef } from 'react'

const computeRmSize = (millingSize, stockMm, roundingMm) => {
  if (!millingSize) return ''
  const parts = millingSize.toLowerCase().split('x').map(p => parseFloat(p.trim()))
  if (parts.length !== 3 || parts.some(isNaN)) return millingSize
  const s = parseFloat(stockMm) || 0
  const r = parseFloat(roundingMm) || 0
  const updated = parts.map(v => {
    let nv = v + s
    if (r > 0) nv = Math.ceil(nv / r) * r
    return nv
  })
  return updated.join(' x ')
}

const parseSize = (sizeStr) => {
  if (!sizeStr) return { l: '', w: '', h: '' }
  const parts = sizeStr.toLowerCase().split('x').map(p => p.trim())
  return {
    l: parts[0] || '',
    w: parts[1] || '',
    h: parts[2] || ''
  }
}

const getNameSuggestions = (row) => {
    const s = new Set()
    if (row.instanceName) s.add(row.instanceName)
    if (row.name) s.add(row.name)
    if (row.partNumber) s.add(row.partNumber)
    return Array.from(s)
}

export default function BOMEditor({ items, onUpdate, onExport, disabled, isFullscreen }) {
  const [activeFilter, setActiveFilter] = useState('all')
  const [showBulkActions, setShowBulkActions] = useState(false)
  const [bulkStock, setBulkStock] = useState(5)
  const [bulkRounding, setBulkRounding] = useState(5)
  const [isCompactView, setIsCompactView] = useState(false)
  const [showTechnicalColumns, setShowTechnicalColumns] = useState(false)
  const [isDraftingSidebarOpen, setIsDraftingSidebarOpen] = useState(false)
  
  const [exportError, setExportError] = useState('')
  const [draft2dLoading, setDraft2dLoading] = useState(false)
  const [draft2dFeedback, setDraft2dFeedback] = useState('')
  
  const [axisPreviewLoading, setAxisPreviewLoading] = useState(false)
  const [axisPreviewOk, setAxisPreviewOk] = useState(false)
  const [axisPropagateLoading, setAxisPropagateLoading] = useState(false)
  const [globalDraftingAxisName, setGlobalDraftingAxisName] = useState('AP_AXIS')

  const [draggingRowId, setDraggingRowId] = useState(null)
  const [dropTargetRowId, setDropTargetRowId] = useState(null)

  const filterOptions = [
    { id: 'all', label: 'All Items' },
    { id: 'mfg', label: 'Manufactured' },
    { id: 'std', label: 'Standard' },
    { id: 'selected', label: 'To Export' }
  ]

  const visibleRows = useMemo(() => {
    if (activeFilter === 'all') return items
    if (activeFilter === 'mfg') return items.filter(it => !it.isStd)
    if (activeFilter === 'std') return items.filter(it => it.isStd)
    if (activeFilter === 'selected') return items.filter(it => it.keepInExport)
    return items
  }, [items, activeFilter])

  const mfgCount = items.filter(it => !it.isStd).length
  const stdCount = items.filter(it => it.isStd).length

  const updateRow = (index, field, value) => {
    const next = [...items]
    next[index] = { ...next[index], [field]: value }
    onUpdate(next)
  }

  const updateMillingCell = (index, part, value) => {
    const row = items[index]
    const cur = parseSize(row.millingSize || row.size)
    cur[part] = value
    const nextSize = `${cur.l} x ${cur.w} x ${cur.h}`
    const next = [...items]
    next[index] = { ...next[index], millingSize: nextSize, size: nextSize }
    onUpdate(next)
  }

  const addMachiningStockToAll = (stock, rounding) => {
    const next = items.map(it => {
      if (it.isStd) return it
      return { ...it, machiningStock: stock, roundingMm: rounding }
    })
    onUpdate(next)
    setShowBulkActions(false)
  }

  const addMissingItem = () => {
    const id = `new-${Date.now()}`
    const newItem = {
      id,
      _rowId: id,
      instanceName: 'MANUAL_ENTRY',
      qty: 1,
      keepInExport: true,
      isStd: false,
      sheetCategory: 'Steel',
      description: '',
      partNumber: '',
      material: '',
      millingSize: '100 x 100 x 20'
    }
    onUpdate([...items, newItem])
  }

  const removeRow = (index) => {
    const next = [...items]
    next.splice(index, 1)
    onUpdate(next)
  }

  const setAllSelected = (val) => {
    onUpdate(items.map(it => ({ ...it, keepInExport: val })))
  }

  const moveRowById = (fromId, toId) => {
    const fromIndex = items.findIndex(it => (it._rowId || it.id) === fromId)
    const toIndex = items.findIndex(it => (it._rowId || it.id) === toId)
    if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) return
    const next = [...items]
    const [row] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, row)
    onUpdate(next)
  }

  const handleExport = async () => {
    setExportError('')
    try {
      await onExport()
    } catch (err) {
      setExportError(err.message || 'Export failed')
    }
  }

  const reviewOptions = ['needs_review', 'approved']
  const discrepancyOptions = ['', 'size_mismatch', 'missing_bodies', 'wrong_category']

  const normalizeFlags = (f) => Array.isArray(f) ? f : []

  const previewDraftingAxis = async (useSelection = false) => {
     setAxisPreviewLoading(true)
     setAxisPreviewOk(false)
     try {
       const res = await fetch('/api/catia/drafting/preview-axis', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           axisName: useSelection ? '' : globalDraftingAxisName,
           useSelection
         })
       })
       const data = await res.json()
       if (data.ok) {
         setAxisPreviewOk(true)
         setDraft2dFeedback(`✓ Axis "${data.foundName}" resolved in active document.`)
       } else {
         setDraft2dFeedback(`✕ Axis resolve failed: ${data.error}`)
       }
     } catch (err) {
       setDraft2dFeedback(`✕ Network error: ${err.message}`)
     } finally {
       setAxisPreviewLoading(false)
     }
  }

  const propagateAxisToMfgParts = async () => {
    setAxisPropagateLoading(true)
    try {
      const mfgItems = items.filter(it => !it.isStd && it.includeIn2dDrawing)
      if (!mfgItems.length) {
        setDraft2dFeedback('✕ Select at least one part in "2D" column first.')
        return
      }
      const res = await fetch('/api/catia/drafting/propagate-axis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          axisName: globalDraftingAxisName,
          items: mfgItems
        })
      })
      const data = await res.json()
      setDraft2dFeedback(`✓ Propagated axis to ${data.count || 0} parts. ${data.errors ? `(${data.errors} failed)` : ''}`)
    } catch (err) {
      setDraft2dFeedback(`✕ Propagation failed: ${err.message}`)
    } finally {
      setAxisPropagateLoading(false)
    }
  }

  const generate2dViews = async (opts = {}) => {
    setDraft2dLoading(true)
    setDraft2dFeedback('Starting 2D layout generation...')
    try {
      const payloadItems = items.filter(it => it.includeIn2dDrawing)
      if (!payloadItems.length) {
        setDraft2dFeedback('✕ Select items in the "2D" column first.')
        setDraft2dLoading(false)
        return
      }

      const res = await fetch('/api/catia/drafting/multi-layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: payloadItems,
          globalDraftingAxisName: opts.useSelection ? '' : globalDraftingAxisName,
          globalDraftingAxisUseSelection: !!opts.useSelection,
          topViewRotationDeg: -90,
          planProjectionUseLeft: true
        })
      })
      const data = await res.json()
      if (data.error) {
        setDraft2dFeedback(`✕ Failed: ${data.error}`)
      } else {
        const warn = (data.warnings || []).length ? `\n⚠️ Warnings: ${data.warnings.join(', ')}` : ''
        setDraft2dFeedback(`✓ Drawing "${data.drawing_name}" created with ${data.views_created?.length || 0} views.${warn}`)
      }
    } catch (err) {
      setDraft2dFeedback(`✕ Error: ${err.message}`)
    } finally {
      setDraft2dLoading(false)
    }
  }

  const handleQuickDraft = (row) => {
     setItems(prev => prev.map(it => it._rowId === row._rowId ? { ...it, includeIn2dDrawing: true } : it))
     setIsDraftingSidebarOpen(true)
  }

  const selectMfgFor2d = () => {
    onUpdate(items.map(it => ({ ...it, includeIn2dDrawing: !it.isStd })))
  }

  const clear2dSelection = () => {
    onUpdate(items.map(it => ({ ...it, includeIn2dDrawing: false })))
  }

  return (
    <div className={isFullscreen 
      ? "bom-editor h-full flex flex-col text-zen-text-main antialiased bg-zen-bg" 
      : "bom-editor mt-4 zen-card overflow-hidden flex flex-col"}>
      
      {/* Top Toolbar */}
      <div className={`border-b border-zen-border flex flex-col ${isFullscreen ? 'bg-zen-surface' : 'bg-zen-surface-alt'}`}>
        <div className="flex items-center justify-between px-6 py-3 border-b border-zen-border/50">
          <div className="flex items-center gap-6">
            <div className="flex flex-col">
              <span className="zen-label text-zen-primary">BOM Engine</span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[9px] px-2 py-0.5 rounded-md bg-zen-info/10 text-zen-info border border-zen-info/10 font-bold uppercase tracking-wider">MFG: {mfgCount}</span>
                <span className="text-[9px] px-2 py-0.5 rounded-md bg-zen-warning/10 text-zen-warning border border-zen-warning/10 font-bold uppercase tracking-wider">STD: {stdCount}</span>
              </div>
            </div>
            
            <div className="h-8 w-px bg-zen-border"></div>

            {/* Filter Toggle Group */}
            <div className="flex bg-zen-bg p-1 rounded-full border border-zen-border shadow-sm">
              {filterOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setActiveFilter(option.id)}
                  className={`text-[10px] px-4 py-1.5 rounded-full transition-all duration-300 font-medium ${activeFilter === option.id ? 'bg-zen-primary text-white shadow-md' : 'text-zen-text-muted hover:text-zen-text-main'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1">
              <button type="button" onClick={() => setAllSelected(true)} className="p-2 rounded-full hover:bg-zen-surface-alt text-zen-text-muted hover:text-zen-primary transition-all active:scale-90" title="Select All">
                <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              </button>
              <button type="button" onClick={() => setAllSelected(false)} className="p-2 rounded-full hover:bg-zen-surface-alt text-zen-text-muted hover:text-zen-error transition-all active:scale-90" title="Unselect All">
                <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-4">
             <button 
                onClick={() => setShowBulkActions(!showBulkActions)}
                className={`zen-pill px-4 py-2 text-[10px] border transition-all flex items-center gap-2 ${showBulkActions ? 'bg-zen-primary text-white' : 'bg-zen-surface border-zen-border text-zen-text-dim hover:bg-zen-surface-alt'}`}
             >
               <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
               Bulk Rules
             </button>

             <button 
                onClick={() => setIsCompactView(!isCompactView)}
                className={`text-[10px] px-4 py-2 rounded-full border transition-all font-bold ${isCompactView ? 'bg-zen-success/10 text-zen-success border-zen-success/20' : 'bg-zen-surface border-zen-border text-zen-text-dim hover:bg-zen-surface-alt'}`}
             >
               {isCompactView ? 'Compact' : 'Comfortable'}
             </button>

             <div className="h-6 w-px bg-zen-border"></div>

             <button type="button" onClick={addMissingItem} className="text-[10px] px-4 py-2 rounded-full bg-zen-surface-alt border border-zen-border hover:bg-zen-border text-zen-text-main font-bold transition-all">+ Row</button>
             
             <button type="button" onClick={handleExport} disabled={disabled} className="zen-pill px-6 py-2 text-[10px] disabled:opacity-50">
               Export Excel
             </button>
          </div>
        </div>

        {/* Secondary Bulk Actions Toolbar */}
        {showBulkActions && (
          <div className="px-6 py-3 bg-zen-info/[0.03] border-b border-zen-border flex items-center gap-6 animate-in slide-in-from-top-2 duration-300">
            <span className="zen-label text-zen-info">Global RM Stock Rules</span>
            <div className="flex items-center gap-3 bg-zen-surface px-4 py-1.5 rounded-full border border-zen-border shadow-sm">
              <span className="text-[9px] text-zen-text-muted font-bold uppercase tracking-wider">Stock:</span>
              <input type="number" value={bulkStock} onChange={(e) => setBulkStock(e.target.value)} className="w-12 text-xs bg-transparent border-none focus:ring-0 p-0 text-zen-primary font-bold" />
              <div className="w-px h-4 bg-zen-border mx-1"></div>
              <span className="text-[9px] text-zen-text-muted font-bold uppercase tracking-wider">Round:</span>
              <input type="number" value={bulkRounding} onChange={(e) => setBulkRounding(e.target.value)} className="w-10 text-xs bg-transparent border-none focus:ring-0 p-0 text-zen-primary font-bold" />
            </div>
            <button type="button" onClick={() => addMachiningStockToAll(bulkStock, bulkRounding)} className="text-[10px] px-5 py-2 rounded-full bg-zen-info/10 text-zen-info hover:bg-zen-info/20 border border-zen-info/20 transition-all font-bold">Apply to All MFG</button>
            
            <div className="ml-auto flex items-center gap-3">
              <button 
                type="button" 
                onClick={() => setShowTechnicalColumns(!showTechnicalColumns)} 
                className={`text-[10px] px-4 py-2 rounded-full border transition-all font-bold ${showTechnicalColumns ? 'bg-zen-warning/10 text-zen-warning border-zen-warning/20' : 'bg-zen-surface border-zen-border text-zen-text-dim hover:bg-zen-surface-alt'}`}
              >
                {showTechnicalColumns ? 'Hide Tech' : 'Show Tech'}
              </button>
              <button 
                type="button" 
                onClick={() => setIsDraftingSidebarOpen(true)} 
                className="text-[10px] px-5 py-2 rounded-full bg-zen-primary text-white hover:bg-black transition-all font-bold shadow-sm"
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
          <div className="fixed inset-0 bg-black/10 backdrop-blur-sm z-[70] animate-in fade-in transition-all duration-500" onClick={() => setIsDraftingSidebarOpen(false)}></div>
          <div className="fixed inset-y-0 right-0 w-[400px] bg-zen-surface border-l border-zen-border shadow-2xl z-[80] p-8 flex flex-col gap-8 animate-in slide-in-from-right duration-500 glass">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-zen-text-main">2D Drafting Center</h3>
                <p className="text-xs text-zen-text-muted mt-1">Automated batch drawing tools</p>
              </div>
              <button 
                onClick={() => setIsDraftingSidebarOpen(false)}
                className="p-2 hover:bg-zen-surface-alt rounded-full transition-all text-zen-text-muted hover:text-zen-text-main"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            <div className="space-y-6 flex-1 overflow-y-auto pr-2 no-scrollbar">
              <div className="p-5 bg-zen-surface-alt rounded-3xl border border-zen-border">
                <p className="zen-label text-zen-primary mb-4">Bulk Selection</p>
                <div className="grid grid-cols-2 gap-3">
                  <button type="button" onClick={selectMfgFor2d} className="text-[10px] px-4 py-2.5 rounded-full bg-zen-primary text-white hover:bg-black transition-all font-bold shadow-sm">
                    Select MFG
                  </button>
                  <button type="button" onClick={clear2dSelection} className="text-[10px] px-4 py-2.5 rounded-full bg-zen-bg border border-zen-border hover:bg-zen-surface-alt text-zen-text-dim transition-all font-bold">
                    Clear All
                  </button>
                </div>
              </div>

              <div className="p-5 bg-zen-surface-alt rounded-3xl border border-zen-border">
                <p className="zen-label text-zen-primary mb-4">Drafting Axis</p>
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-[9px] text-zen-text-muted font-bold uppercase tracking-wider ml-1">Axis Name</label>
                    <input
                      type="text"
                      placeholder="e.g. AP_AXIS"
                      value={globalDraftingAxisName}
                      onChange={(e) => setGlobalDraftingAxisName(e.target.value)}
                      className="w-full text-xs bg-zen-bg border border-zen-border rounded-xl px-4 py-3 placeholder:text-zen-text-muted/30 focus:border-zen-primary transition-all outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-2.5">
                    <button
                      type="button"
                      onClick={() => previewDraftingAxis(false)}
                      disabled={disabled || axisPreviewLoading || draft2dLoading}
                      className="text-[11px] py-3 rounded-full bg-zen-bg border border-zen-border hover:bg-zen-surface-alt disabled:opacity-50 transition-all font-bold text-zen-text-main"
                    >
                      {axisPreviewLoading ? 'Searching…' : 'Preview By Name'}
                    </button>
                    <button
                      type="button"
                      onClick={() => previewDraftingAxis(true)}
                      disabled={disabled || axisPreviewLoading || draft2dLoading}
                      className="text-[11px] py-3 rounded-full bg-zen-bg border border-zen-border hover:bg-zen-surface-alt disabled:opacity-50 transition-all font-bold text-zen-text-main"
                    >
                      Preview Selection
                    </button>
                    <button
                      type="button"
                      onClick={propagateAxisToMfgParts}
                      disabled={disabled || !axisPreviewOk || axisPreviewLoading || axisPropagateLoading || draft2dLoading}
                      className="text-[11px] py-3.5 rounded-full bg-zen-primary text-white hover:bg-black disabled:opacity-30 transition-all font-bold mt-2 shadow-[0_8px_24px_-4px_rgba(26,26,26,0.2)]"
                    >
                      {axisPropagateLoading ? 'Propagating…' : 'Apply Axis to All Parts'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-5 bg-zen-success/[0.03] rounded-3xl border border-zen-success/10">
                <p className="zen-label text-zen-success mb-4">Generation</p>
                <div className="space-y-3">
                  <button
                    type="button"
                    onClick={() => generate2dViews()}
                    disabled={disabled || draft2dLoading}
                    className="w-full text-xs py-4 rounded-full bg-zen-success text-white hover:opacity-90 disabled:opacity-50 transition-all font-bold shadow-[0_8px_24px_-4px_rgba(16,185,129,0.2)]"
                  >
                    {draft2dLoading ? 'Generating Views…' : 'Generate 2D Layout'}
                  </button>
                  <button
                    type="button"
                    onClick={() => generate2dViews({ useSelection: true })}
                    disabled={disabled || draft2dLoading}
                    className="w-full text-[10px] py-2.5 rounded-full bg-zen-success/10 text-zen-success border border-zen-success/20 hover:bg-zen-success/20 transition-all font-bold"
                  >
                    Quick Gen (Selection)
                  </button>
                </div>
              </div>
            </div>
            
            <div className="mt-auto p-5 bg-zen-surface-alt rounded-2xl border border-zen-border/50">
              <p className="text-[10px] text-zen-text-muted leading-relaxed italic">
                <strong>Tip:</strong> Select the target parts in the "2D" column of the main table before triggering generation.
              </p>
            </div>
          </div>
        </>
      )}

      {exportError && (
        <div className="px-6 py-2.5 text-[11px] text-zen-warning bg-zen-warning/10 border-b border-zen-warning/20 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          {exportError}
        </div>
      )}
      {draft2dFeedback && (
        <div className="px-6 py-3 text-[11px] text-zen-success bg-zen-success/[0.03] border-b border-zen-success/10 whitespace-pre-wrap font-mono">
          {draft2dFeedback}
        </div>
      )}

      <div className={`overflow-x-auto overflow-y-auto no-scrollbar ${isFullscreen ? 'flex-1 h-full' : 'max-h-[70vh]'}`}>
        <table className="w-full text-[11px] border-collapse min-w-max">
          <thead className="sticky top-0 bg-zen-surface z-40 border-b border-zen-border">
            <tr className="bg-zen-surface-alt/50">
              <th className="w-10 py-3 px-2"></th>
              <th className="w-10 py-3 px-1 text-center font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Exp</th>
              <th className={`${isCompactView ? 'w-10' : 'w-14'} py-3 px-1 text-center font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]`}>2D</th>
              <th className="w-24 py-3 px-4 text-left font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Qty</th>
              <th className="text-left py-3 px-5 min-w-[160px] sticky-column sticky-left-instance bg-zen-surface-alt font-bold text-zen-primary uppercase tracking-widest text-[9px]">Part Instance</th>
              <th className="text-left py-3 px-4 min-w-[140px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Section</th>
              <th className="text-left py-3 px-4 min-w-[200px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Description</th>
              <th className="text-left py-3 px-4 min-w-[180px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Part / Catalog</th>
              <th className="text-left py-3 px-4 min-w-[100px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Type</th>
              <th className="text-left py-3 px-4 min-w-[140px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Mat / Mfg</th>
              <th className="text-left py-3 px-4 min-w-[120px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Remark</th>
              <th className="text-left py-3 px-4 min-w-[110px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Status</th>
              
              {showTechnicalColumns && (
                <>
                  <th className="text-left py-3 px-4 min-w-[130px] font-bold text-zen-warning uppercase tracking-tighter text-[9px]">Issue</th>
                  <th className="text-left py-3 px-4 min-w-[80px] font-bold text-zen-warning uppercase tracking-tighter text-[9px]">Method</th>
                </>
              )}

              <th className="text-left py-3 px-3 min-w-[70px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">L</th>
              <th className="text-left py-3 px-3 min-w-[70px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">W</th>
              <th className="text-left py-3 px-3 min-w-[70px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">H</th>
              <th className="text-left py-3 px-3 min-w-[70px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Stk</th>
              <th className="text-left py-3 px-3 min-w-[70px] font-bold text-zen-text-muted uppercase tracking-tighter text-[9px]">Rnd</th>
              <th className="text-left py-3 px-5 min-w-[150px] font-bold text-zen-info uppercase tracking-widest text-[9px]">RM SIZE</th>

              {showTechnicalColumns && (
                <>
                  <th className="text-left py-4 px-4 w-24 font-bold text-zen-info/60 uppercase tracking-tighter text-[9px]">RM L</th>
                  <th className="text-left py-4 px-4 w-24 font-bold text-zen-info/60 uppercase tracking-tighter text-[9px]">RM W</th>
                  <th className="text-left py-4 px-4 w-24 font-bold text-zen-info/60 uppercase tracking-tighter text-[9px]">RM H</th>
                  <th className="text-left py-4 px-4 min-w-[100px] font-bold text-zen-warning/60 uppercase tracking-tighter text-[9px]">Conf</th>
                  <th className="text-left py-4 px-4 min-w-[200px] font-bold text-zen-warning/60 uppercase tracking-tighter text-[9px]">Technical Notes</th>
                </>
              )}
              <th className="w-12" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zen-border/50">
            {visibleRows.map((row, vIndex) => {
              const actualIndex = items.findIndex((candidate) => candidate._rowId === row._rowId)
              const rowKey = row._rowId ?? `vrow-${vIndex}`
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
                  className={`bom-table-row transition-all duration-200 group relative ${
                    draggingRowId != null && String(draggingRowId) === String(rowKey) ? 'opacity-30' : ''
                  } ${isDragOver ? 'bg-zen-info/10' : 'hover:bg-zen-surface-alt/50'} ${isCompactView ? 'text-[11px]' : 'text-xs'}`}
                >
                  <td className="sticky-column sticky-left-handle py-1 px-1 align-middle bg-zen-surface-alt/80 backdrop-blur-sm z-10">
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
                      className="inline-flex cursor-grab active:cursor-grabbing text-zen-text-muted/30 group-hover:text-zen-primary p-1.5 rounded-lg hover:bg-zen-surface transition-all outline-none"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" /></svg>
                    </span>
                  </td>
                  <td className={`py-1 px-1 bg-zen-surface-alt/80 backdrop-blur-sm text-center ${isCompactView ? 'w-8' : 'w-10'}`}>
                    <input type="checkbox" checked={row.keepInExport} onChange={(e) => updateRow(actualIndex, 'keepInExport', e.target.checked)} className="w-3.5 h-3.5 rounded border-zen-border bg-zen-bg checked:bg-zen-primary transition-all cursor-pointer" />
                  </td>
                  <td className={`py-1 px-1 text-center ${isCompactView ? 'w-10' : 'w-14'}`}>
                    <div className="flex items-center justify-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={row.includeIn2dDrawing === true}
                        onChange={(e) => updateRow(actualIndex, 'includeIn2dDrawing', e.target.checked)}
                        className="w-3.5 h-3.5 rounded border-zen-border bg-zen-bg checked:bg-zen-success transition-all cursor-pointer"
                      />
                      <button 
                        onClick={() => handleQuickDraft(row)}
                        className="p-1 text-zen-text-muted/40 hover:text-zen-info transition-all rounded hover:bg-zen-surface"
                        title="Quick 2D Draft"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                      </button>
                    </div>
                  </td>
                  <td className="py-1 px-2">
                    <input type="number" min="1" value={row.qty || 1} onChange={(e) => updateRow(actualIndex, 'qty', e.target.value)} className={`w-14 bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-zen-text-main font-bold`} />
                  </td>
                  <td className={`sticky-column sticky-left-instance py-1 px-5 bg-zen-surface-alt/80 backdrop-blur-sm font-mono text-zen-primary font-bold truncate max-w-[200px] ${isCompactView ? 'text-[9px]' : 'text-[10px]'}`} title={row.instanceName || row.name}>
                    {row.instanceName || row.name}
                  </td>
                  <td className="py-1 px-1">
                    <input
                      type="text"
                      value={row.parentAssembly || ''}
                      onChange={(e) => updateRow(actualIndex, 'parentAssembly', e.target.value)}
                      placeholder="—"
                      className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} font-mono placeholder:text-zen-text-muted/20 transition-all outline-none`}
                    />
                  </td>
                  <td className="py-1 px-1">
                    <input list={datalistId} type="text" value={row.description || ''} onChange={(e) => updateRow(actualIndex, 'description', e.target.value)} placeholder="Description" className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-zen-text-main`} />
                    <datalist id={datalistId}>
                      {suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
                    </datalist>
                  </td>
                  <td className="py-1 px-1">
                    <div className="flex flex-col gap-0.5">
                      <input type="text" value={row.partNumber || ''} onChange={(e) => updateRow(actualIndex, 'partNumber', e.target.value)} placeholder="Part No" className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-zen-text-dim`} />
                      {isStd && (
                        <input type="text" value={row.catalogCode || ''} onChange={(e) => updateRow(actualIndex, 'catalogCode', e.target.value)} placeholder="Catalog" className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0 text-[8px]' : 'py-0.5 text-[9px]'} font-mono placeholder:text-zen-text-muted/10 transition-all outline-none text-zen-text-muted`} />
                      )}
                    </div>
                  </td>
                  <td className="py-1 px-1">
                    <div className="flex flex-col gap-1">
                      <button
                        type="button"
                        onClick={() => updateRow(actualIndex, 'isStd', !isStd)}
                        className={`text-[8px] font-bold px-2 py-0.5 rounded-md border tracking-widest transition-all ${isStd ? 'bg-zen-warning/10 text-zen-warning border-zen-warning/10' : 'bg-zen-primary text-white border-zen-primary'}`}
                      >
                        {isStd ? 'STD' : 'MFG'}
                      </button>
                      <select value={row.sheetCategory || ''} onChange={(e) => updateRow(actualIndex, 'sheetCategory', e.target.value)} className="w-full bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg text-[9px] px-1 py-0.5 outline-none cursor-pointer rounded">
                        {availableSheetOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </div>
                  </td>
                  <td className="py-1 px-1">
                    <input
                      type="text"
                      value={isStd ? (row.manufacturer || '') : (row.material || '')}
                      onChange={(e) => updateRow(actualIndex, isStd ? 'manufacturer' : 'material', e.target.value)}
                      placeholder={isStd ? "Manufacturer" : "Material"}
                      className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} outline-none transition-all ${materialRequired && !`${row.material || ''}`.trim() ? 'bg-zen-error/5 text-zen-error' : 'text-zen-text-main'}`}
                    />
                  </td>
                  <td className="py-1 px-1 text-center">
                    <input type="text" value={row.remark || ''} onChange={(e) => updateRow(actualIndex, 'remark', e.target.value)} placeholder="—" className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-2 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} transition-all outline-none text-zen-text-dim`} />
                  </td>
                  <td className="py-1 px-1">
                    <select value={row.reviewStatus || 'needs_review'} onChange={(e) => updateRow(actualIndex, 'reviewStatus', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[9px]' : 'py-1 text-[10px]'} outline-none cursor-pointer uppercase font-bold tracking-widest text-[8px] ${row.reviewStatus === 'approved' ? 'text-zen-success' : 'text-zen-warning'}`}>
                      {reviewOptions.map((option) => <option key={option} value={option}>{option.replace('_', ' ')}</option>)}
                    </select>
                  </td>

                  {showTechnicalColumns && (
                    <>
                      <td className="py-1 px-1">
                        <select value={row.discrepancyType || ''} onChange={(e) => updateRow(actualIndex, 'discrepancyType', e.target.value)} className="w-full bg-transparent border-transparent hover:border-zen-border focus:bg-zen-bg text-[9px] px-1 py-0.5 outline-none text-zen-warning font-bold uppercase tracking-tighter">
                          {discrepancyOptions.map((option) => <option key={option || 'none'} value={option}>{option || 'No Issue'}</option>)}
                        </select>
                      </td>
                      <td className="py-1 px-1 font-mono text-[9px] text-zen-text-muted uppercase text-center font-bold">{row.methodUsed || '—'}</td>
                    </>
                  )}

                  <td className="py-1 px-1"><input type="text" value={milling.l} onChange={(e) => updateMillingCell(actualIndex, 'l', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center text-zen-text-main`} /></td>
                  <td className="py-1 px-1"><input type="text" value={milling.w} onChange={(e) => updateMillingCell(actualIndex, 'w', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center text-zen-text-main`} /></td>
                  <td className="py-1 px-1"><input type="text" value={milling.h} onChange={(e) => updateMillingCell(actualIndex, 'h', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} font-mono transition-all outline-none text-center text-zen-text-main`} /></td>
                  <td className="py-1 px-1"><input type="number" value={row.machiningStock || ''} onChange={(e) => updateRow(actualIndex, 'machiningStock', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-center text-zen-text-muted hover:text-zen-primary font-bold`} /></td>
                  <td className="py-1 px-1"><input type="number" value={row.roundingMm || ''} onChange={(e) => updateRow(actualIndex, 'roundingMm', e.target.value)} className={`w-full bg-transparent border-transparent hover:border-zen-border focus:border-zen-primary/50 focus:bg-zen-bg rounded-md px-1 ${isCompactView ? 'py-0.5 text-[10px]' : 'py-1 text-xs'} transition-all outline-none text-center text-zen-text-muted hover:text-zen-primary font-bold`} /></td>
                  
                  <td className={`py-1 px-5 font-mono font-bold bg-zen-info/[0.03] text-zen-info border-x border-zen-info/10 ${isCompactView ? 'text-[10px]' : 'text-xs'}`}>{row.rmSize || '—'}</td>

                  {showTechnicalColumns && (
                    <>
                      <td className={`py-1 px-4 font-mono text-zen-info/50 text-center ${isCompactView ? 'text-[8px]' : 'text-[9px]'}`}>{rm.l}</td>
                      <td className="py-3 px-4 font-mono text-[10px] text-zen-info/50">{rm.w}</td>
                      <td className="py-3 px-4 font-mono text-[10px] text-zen-info/50">{rm.h}</td>
                      <td className={`py-3 px-4 text-[9px] uppercase font-bold tracking-widest ${row.measurementConfidence === 'high' ? 'text-zen-success' : 'text-zen-warning'}`}>{row.measurementConfidence || 'low'}</td>
                      <td className="py-3 px-4 text-[9px] text-zen-text-muted space-y-2">
                        <div className="font-bold flex gap-2 flex-wrap">
                          {normalizeFlags(row.validationFlags).length ? normalizeFlags(row.validationFlags).map(f => (
                            <span key={f} className="px-1.5 py-0.5 bg-zen-warning/10 text-zen-warning rounded uppercase text-[8px]">{f}</span>
                          )) : <span className="text-zen-success uppercase text-[8px] tracking-widest">Validated</span>}
                        </div>
                        <input type="text" value={row.reviewNote || ''} onChange={(e) => updateRow(actualIndex, 'reviewNote', e.target.value)} placeholder="Audit note..." className="w-full min-w-[160px] text-[10px] bg-zen-surface-alt border border-zen-border rounded-lg px-3 py-1.5 text-zen-text-main focus:border-zen-primary outline-none" />
                      </td>
                    </>
                  )}
                  
                  <td className="py-3 px-2">
                    {row.id?.toString().startsWith('new-') && (
                      <button type="button" onClick={() => removeRow(actualIndex)} className="p-2 hover:bg-zen-error/10 text-zen-error/40 hover:text-zen-error transition-all rounded-full" title="Remove Row">
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
