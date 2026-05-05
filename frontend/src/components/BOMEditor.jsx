import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { DataGrid, SelectColumn } from 'react-data-grid'
import 'react-data-grid/lib/styles.css'

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

export default function BOMEditor({ items, onUpdate, onExport, disabled, isFullscreen }) {
  const [activeFilter, setActiveFilter] = useState('all')
  const [showBulkActions, setShowBulkActions] = useState(false)
  const [bulkStock, setBulkStock] = useState(5)
  const [bulkRounding, setBulkRounding] = useState(5)
  const [isCompactView, setIsCompactView] = useState(true) 
  const [showTechnicalColumns, setShowTechnicalColumns] = useState(false)
  const [isDraftingSidebarOpen, setIsDraftingSidebarOpen] = useState(false)
  const [selectedRows, setSelectedRows] = useState(() => new Set(items.map(it => it._rowId || it.id || it.sourceRowId)))
  
  const [exportError, setExportError] = useState('')
  const [draft2dLoading, setDraft2dLoading] = useState(false)
  const [draft2dFeedback, setDraft2dFeedback] = useState('')
  
  const [axisPreviewLoading, setAxisPreviewLoading] = useState(false)
  const [axisPreviewOk, setAxisPreviewOk] = useState(false)
  const [axisPropagateLoading, setAxisPropagateLoading] = useState(false)
  const [globalDraftingAxisName, setGlobalDraftingAxisName] = useState('AP_AXIS')

  const filterOptions = [
    { id: 'all', label: 'All Items' },
    { id: 'mfg', label: 'Manufactured' },
    { id: 'std', label: 'Standard' },
    { id: 'selected', label: 'To Export' }
  ]

  const mfgCount = items.filter(it => !it.isStd).length
  const stdCount = items.filter(it => it.isStd).length

  const gridRows = useMemo(() => {
    const filtered = activeFilter === 'all' ? items :
                     activeFilter === 'mfg' ? items.filter(it => !it.isStd) :
                     activeFilter === 'std' ? items.filter(it => it.isStd) :
                     activeFilter === 'selected' ? items.filter(it => it.keepInExport) : items
    
    return filtered.map((it, idx) => {
      const s = parseSize(it.millingSize || it.size)
      return {
        ...it,
        _gridKey: it._rowId || it.id || it.sourceRowId || `fallback-${idx}`,
        _l: s.l,
        _w: s.w,
        _h: s.h,
        material: it.isStd ? (it.manufacturer || '') : (it.material || '')
      }
    })
  }, [items, activeFilter])

  const handleRowsChange = useCallback((newRows, { indexes, column }) => {
    const nextItems = [...items]
    indexes.forEach(idx => {
      const gridRow = newRows[idx]
      const originalIndex = items.findIndex(it => (it._rowId || it.id || it.sourceRowId) === (gridRow._rowId || gridRow.id || gridRow.sourceRowId))
      if (originalIndex === -1) return

      let updatedRow = { ...gridRow }
      
      if (['_l', '_w', '_h'].includes(column.key)) {
        updatedRow.millingSize = `${updatedRow._l} x ${updatedRow._w} x ${updatedRow._h}`
        updatedRow.size = updatedRow.millingSize
      }

      if (column.key === 'material') {
        if (updatedRow.isStd) {
          updatedRow.manufacturer = gridRow.material;
        } else {
          updatedRow.material = gridRow.material;
        }
      }

      nextItems[originalIndex] = updatedRow
    })
    onUpdate(nextItems)
  }, [items, onUpdate]);

  useEffect(() => {
    // If items count changes, ensure new items are selected
    const allKeys = items.map(it => it._rowId || it.id || it.sourceRowId);
    setSelectedRows(prev => {
        const next = new Set(prev);
        allKeys.forEach(k => {
            if (!next.has(k)) next.add(k);
        });
        return next;
    });
  }, [items.length]);

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
      millingSize: '100 x 100 x 20',
      hardness: ''
    }
    onUpdate([...items, newItem])
  }

  const addMachiningStockToAll = (stock, rounding) => {
    const next = items.map(it => {
      if (it.isStd) return it
      return { ...it, machiningStock: stock, roundingMm: rounding }
    })
    onUpdate(next)
    setShowBulkActions(false)
  }

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitFeedback, setSubmitFeedback] = useState('')

  const handleSubmitForReview = async () => {
    if (!selectedRows.size) {
      setSubmitFeedback('✕ Select items to submit.')
      return
    }
    
    setIsSubmitting(true)
    setSubmitFeedback('')
    
    try {
      const itemsToSubmit = items.filter(it => selectedRows.has(it._rowId || it.id || it.sourceRowId))
      const res = await fetch('/api/bom/submit-review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: itemsToSubmit,
          projectId: items[0]?.projectId || 'P-001', // Fallback or from metadata
          toolId: items[0]?.toolId || 'T-001',
          projectName: items[0]?.projectName || 'Unknown Project',
          comment: `Submitted for review via CADMation Copilot. Total items: ${itemsToSubmit.length}`
        })
      })
      
      const data = await res.json()
      if (data.success) {
        setSubmitFeedback('✓ BOM submitted to Design Lead successfully.')
      } else {
        setSubmitFeedback(`✕ Submission failed: ${data.detail || data.error}`)
      }
    } catch (err) {
      setSubmitFeedback(`✕ Network error: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleExport = async () => {
    setExportError('')
    try {
      const itemsToExport = items.filter(it => selectedRows.has(it._rowId || it.id || it.sourceRowId))
      await onExport(itemsToExport)
    } catch (err) {
      setExportError(err.message || 'Export failed')
    }
  }

  const handleQuickDraft = (row) => {
     const rid = row._rowId || row.id || row.sourceRowId
     onUpdate(items.map(it => (it._rowId || it.id || it.sourceRowId) === rid ? { ...it, includeIn2dDrawing: true } : it))
     setIsDraftingSidebarOpen(true)
  }

  const columns = useMemo(() => [
    { ...SelectColumn, width: 35, resizable: true },
    { key: 'qty', name: 'Qty', width: 45, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'instanceName', name: 'Instance', width: 140, resizable: true, renderCell: ({ row }) => <span className="font-mono text-zen-primary font-bold text-[10px]">{row.instanceName || row.name}</span> },
    { key: 'parentAssembly', name: 'Section', width: 100, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'description', name: 'Description', width: 160, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'partNumber', name: 'Part / Catalog', width: 140, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { 
      key: 'isStd', 
      name: 'Type', 
      width: 60,
      resizable: true,
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
      name: 'Category', 
      width: 70,
      resizable: true,
      cellClass: 'editable-cell dropdown-cell',
      renderEditCell: ({ row, onRowChange }) => (
        <select 
          value={row.sheetCategory || ''} 
          onChange={(e) => onRowChange({ ...row, sheetCategory: e.target.value })}
          className="w-full bg-zen-surface text-[10px] h-full outline-none"
          autoFocus
        >
          {(row.isStd ? ['STD'] : ['Steel', 'MS', 'Casting']).map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      )
    },
    { 
      key: 'material', 
      name: 'Mat/Mfg', 
      width: 120, 
      resizable: true,
      cellClass: 'editable-cell',
      renderEditCell: textEditor,
      renderCell: ({ row }) => row.isStd ? (row.manufacturer || '') : (row.material || '')
    },
    { key: '_l', name: 'L', width: 50, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: '_w', name: 'W', width: 50, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: '_h', name: 'H', width: 50, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'machiningStock', name: 'Stk', width: 45, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'roundingMm', name: 'Rnd', width: 45, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { 
      key: 'rmSize', 
      name: 'RM SIZE', 
      width: 140, 
      resizable: true,
      renderCell: ({ row }) => <span className="font-mono text-[9px] text-zen-info font-bold">{computeRmSize(row.millingSize || row.size, row.machiningStock, row.roundingMm)}</span>
    },
    { key: 'hardness', name: 'Hardness', width: 80, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    { key: 'remark', name: 'Remark', width: 120, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
    ...(showTechnicalColumns ? [
      { key: 'discrepancyType', name: 'Issue', width: 100, renderEditCell: textEditor, resizable: true, cellClass: 'editable-cell' },
      { key: 'methodUsed', name: 'Method', width: 70, resizable: true, renderCell: ({ row }) => <span className="font-mono text-[9px] uppercase">{row.methodUsed}</span> }
    ] : [])
  ], [gridRows, showTechnicalColumns])

  return (
    <div className={isFullscreen 
      ? "bom-editor h-full flex flex-col text-zen-text-main antialiased bg-zen-bg" 
      : "bom-editor mt-4 zen-card overflow-hidden flex flex-col"}>
      
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

            <div className="flex bg-zen-bg p-1 rounded-full border border-zen-border shadow-sm">
              {filterOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setActiveFilter(option.id)}
                  className={`text-[10px] px-4 py-1.5 rounded-full transition-all duration-300 font-medium ${activeFilter === option.id ? 'bg-zen-primary text-white shadow-md' : 'text-zen-text-muted hover:text-zen-text-main'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {submitFeedback && (
              <span className={`text-[10px] font-bold ${submitFeedback.startsWith('✕') ? 'text-zen-warning' : 'text-zen-success'} animate-in fade-in duration-300`}>
                {submitFeedback}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4">
             <button onClick={() => setShowBulkActions(!showBulkActions)} className={`zen-pill px-4 py-2 text-[10px] border transition-all flex items-center gap-2 ${showBulkActions ? 'bg-zen-primary text-white' : 'bg-zen-surface border-zen-border text-zen-text-dim hover:bg-zen-surface-alt'}`}>
               <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
               Bulk Rules
             </button>

             <button type="button" onClick={addMissingItem} className="text-[10px] px-4 py-2 rounded-full bg-zen-surface-alt border border-zen-border hover:bg-zen-border text-zen-text-main font-bold transition-all">+ Row</button>
             
             <div className="flex items-center gap-2 bg-zen-bg p-1 rounded-full border border-zen-border shadow-sm">
               <button 
                 type="button" 
                 onClick={handleSubmitForReview} 
                 disabled={disabled || isSubmitting} 
                 className={`px-5 py-1.5 rounded-full text-[10px] font-bold uppercase transition-all ${isSubmitting ? 'bg-zen-surface text-zen-text-muted' : 'bg-zen-warning/10 text-zen-warning hover:bg-zen-warning hover:text-white'}`}
               >
                 {isSubmitting ? 'Submitting...' : 'Submit Review'}
               </button>
               <button 
                 type="button" 
                 onClick={handleExport} 
                 disabled={disabled} 
                 className="px-5 py-1.5 rounded-full text-[10px] font-bold uppercase bg-zen-primary text-white hover:bg-black transition-all"
               >
                 Export Excel
               </button>
             </div>
          </div>
        </div>

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
              <button onClick={() => setIsDraftingSidebarOpen(true)} className="text-[10px] px-5 py-2 rounded-full bg-zen-primary text-white hover:bg-black transition-all font-bold shadow-sm">Drafting Assistant</button>
            </div>
          </div>
        )}
      </div>

      <div className={`flex-1 overflow-hidden rdg-zen-container ${isFullscreen ? '' : 'min-h-[500px]'}`}>
        <DataGrid
          columns={columns}
          rows={gridRows}
          onRowsChange={handleRowsChange}
          rowKeyGetter={(row) => row._gridKey}
          selectedRows={selectedRows}
          onSelectedRowsChange={setSelectedRows}
          onCellClick={({ row, column, selectCell }) => {
            if (column.key === 'isStd') {
              const rowIndex = gridRows.findIndex(r => (r._rowId || r.id || r.sourceRowId) === (row._rowId || row.id || row.sourceRowId));
              if (rowIndex === -1) return;
              const nextRows = gridRows.map((r, idx) => idx === rowIndex ? { ...r, isStd: !r.isStd } : r);
              handleRowsChange(nextRows, { indexes: [rowIndex], column: { key: 'isStd' } });
            } else if (column.renderEditCell) {
              selectCell(true);
            }
          }}
          rowHeight={isCompactView ? 30 : 40}
          headerRowHeight={35}
          className="rdg-light fill-grid"
          style={{ height: '100%' }}
        />
      </div>

      {isDraftingSidebarOpen && (
        <DraftingSidebar 
          onClose={() => setIsDraftingSidebarOpen(false)} 
          globalDraftingAxisName={globalDraftingAxisName}
          setGlobalDraftingAxisName={setGlobalDraftingAxisName}
          items={items}
          onUpdate={onUpdate}
          disabled={disabled}
        />
      )}

      {exportError && (
        <div className="px-6 py-2.5 text-[11px] text-zen-warning bg-zen-warning/10 border-t border-zen-warning/20 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          {exportError}
        </div>
      )}
    </div>
  )
}

function DraftingSidebar({ onClose, globalDraftingAxisName, setGlobalDraftingAxisName, items, onUpdate, disabled }) {
  const [feedback, setFeedback] = useState('')
  const [loading, setLoading] = useState(false)
  const [axisOk, setAxisOk] = useState(false)

  const previewAxis = async (useSelection = false) => {
     setLoading(true)
     setAxisOk(false)
     try {
       const res = await fetch('/api/catia/drafting/preview-axis', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ axisName: useSelection ? '' : globalDraftingAxisName, useSelection })
       })
       const data = await res.json()
       if (data.ok) {
         setAxisOk(true)
         setFeedback(`✓ Axis "${data.foundName}" resolved.`)
       } else {
         setFeedback(`✕ Axis failed: ${data.error}`)
       }
     } catch (err) {
       setFeedback(`✕ Error: ${err.message}`)
     } finally {
       setLoading(false)
     }
  }

  const generate = async (opts = {}) => {
    setLoading(true)
    setFeedback('Starting...')
    try {
      const payloadItems = items.filter(it => it.includeIn2dDrawing)
      if (!payloadItems.length) {
        setFeedback('✕ No items selected in 2D column.')
        setLoading(false)
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
      if (data.error) setFeedback(`✕ Failed: ${data.error}`)
      else setFeedback(`✓ Created "${data.drawing_name}" with ${data.views_created?.length || 0} views.`)
    } catch (err) {
      setFeedback(`✕ Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/10 backdrop-blur-sm z-[70]" onClick={onClose}></div>
      <div className="fixed inset-y-0 right-0 w-[400px] bg-zen-surface border-l border-zen-border shadow-2xl z-[80] p-8 flex flex-col gap-8 glass">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold">2D Drafting Center</h3>
          <button onClick={onClose} className="p-2 hover:bg-zen-surface-alt rounded-full"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
        </div>
        <div className="space-y-6 flex-1 overflow-y-auto pr-2 no-scrollbar">
          <button onClick={() => onUpdate(items.map(it => ({ ...it, includeIn2dDrawing: !it.isStd })))} className="w-full text-[10px] py-2.5 rounded-full bg-zen-primary text-white font-bold">Select MFG</button>
          <div className="p-5 bg-zen-surface-alt rounded-3xl border border-zen-border space-y-4">
            <p className="zen-label">Drafting Axis</p>
            <input type="text" value={globalDraftingAxisName} onChange={(e) => setGlobalDraftingAxisName(e.target.value)} className="w-full text-xs bg-zen-bg border border-zen-border rounded-xl px-4 py-3 outline-none" />
            <button onClick={() => previewAxis(false)} disabled={disabled || loading} className="w-full text-[11px] py-3 rounded-full bg-zen-bg border border-zen-border font-bold">Preview Axis</button>
            <button onClick={() => generate()} disabled={disabled || loading} className="w-full text-xs py-4 rounded-full bg-zen-success text-white font-bold shadow-lg">Generate 2D Layout</button>
          </div>
        </div>
        {feedback && <div className="p-4 text-[10px] text-zen-success bg-zen-success/[0.03] border border-zen-success/10 rounded-xl font-mono whitespace-pre-wrap">{feedback}</div>}
      </div>
    </>
  )
}
