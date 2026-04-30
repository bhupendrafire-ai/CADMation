import { useState, useCallback, useMemo } from 'react'

export default function DraftingPage({ activeDoc, isConnected, lastBomMsg }) {
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [axisName, setAxisName] = useState('')
  const [rotation, setRotation] = useState(-90)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Use editor-stage items (post-measurement), fall back to selector items
  const allItems = useMemo(() => {
    const editorItems = lastBomMsg?.bomEditor?.items
    const selectorItems = lastBomMsg?.interactive?.items
    return editorItems || selectorItems || []
  }, [lastBomMsg])

  // Only show MFG items
  const mfgItems = useMemo(() => allItems.filter(item => !item.isStd), [allItems])

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return mfgItems
    const q = searchQuery.toLowerCase()
    return mfgItems.filter(item =>
      (item.instanceName || item.instance_name || '').toLowerCase().includes(q) ||
      (item.partNumber || item.part_number || '').toLowerCase().includes(q) ||
      (item.description || '').toLowerCase().includes(q)
    )
  }, [mfgItems, searchQuery])

  const rowKey = (item) => item._rowId || item.sourceRowId || item.id || item.instanceName || item.instance_name

  const toggleSelection = (key) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredItems.length && filteredItems.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredItems.map(rowKey)))
    }
  }

  // --- EXACT same logic as BOMEditor.generate2dViews ---
  const generateViews = useCallback(async (useSelection = false) => {
    const payloadItems = mfgItems.filter(it => selectedIds.has(rowKey(it)))
    if (!payloadItems.length) {
      setFeedback('Select at least one MFG item first.')
      return
    }

    setLoading(true)
    setFeedback('')
    try {
      const body = {
        items: payloadItems,
        globalDraftingAxisUseSelection: useSelection,
        topViewRotationDeg: rotation,
        planProjectionUseLeft: true,
      }
      const trimmed = `${axisName || ''}`.trim()
      if (!useSelection && trimmed) body.globalDraftingAxisName = trimmed

      const res = await fetch('/api/catia/drafting/multi-layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (!res.ok) {
        setFeedback(`Failed: ${data.detail || data.error || 'Unknown error'}`)
        return
      }
      if (data.error) {
        setFeedback(`Failed: ${data.error}`)
        return
      }

      const warnings = (data.warnings || []).length ? ` | ${data.warnings.join('; ')}` : ''
      setFeedback(`✓ "${data.drawing_name}" — ${(data.views_created || []).length} view(s)${warnings}`)
    } catch (err) {
      setFeedback(`Request failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [mfgItems, selectedIds, axisName, rotation])

  const allSelected = filteredItems.length > 0 && selectedIds.size === filteredItems.length
  const hasSelection = selectedIds.size > 0

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-zen-bg no-scrollbar">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="px-2 py-0.5 rounded-md bg-zen-info/10 border border-zen-info/20 text-[9px] font-bold text-zen-info uppercase tracking-widest">Enterprise v2.3</div>
            <div className={`px-2 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-widest border ${isConnected ? 'bg-zen-success/10 border-zen-success/20 text-zen-success' : 'bg-zen-error/10 border-zen-error/20 text-zen-error'}`}>
              {isConnected ? (activeDoc || 'Connected') : 'Disconnected'}
            </div>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zen-text-main">2D Drafting Center</h2>
          <p className="text-zen-text-dim text-sm mt-1">Select MFG items from your BOM to generate multi-view drawings in CATIA.</p>
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">

          {/* Item list — takes 3 cols */}
          <div className="lg:col-span-3 space-y-3">

            {/* Search + count bar */}
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zen-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search by name, part number or description…"
                  className="w-full bg-zen-surface border border-zen-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-zen-text-main focus:border-zen-info/50 outline-none transition-all"
                />
              </div>
              <div className="shrink-0 text-xs text-zen-text-muted font-mono">{selectedIds.size}/{mfgItems.length} selected</div>
            </div>

            {/* Table */}
            <div className="zen-card border border-zen-border overflow-hidden">
              {mfgItems.length === 0 ? (
                <div className="py-20 text-center text-zen-text-muted">
                  <svg className="w-10 h-10 mx-auto mb-3 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-sm font-medium">No MFG items found</p>
                  <p className="text-xs mt-1 text-zen-text-muted">Generate a BOM first from the Assembly Tree tab, then come back here.</p>
                </div>
              ) : (
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-zen-border text-[10px] font-bold text-zen-text-muted uppercase tracking-widest bg-zen-surface-alt">
                      <th className="py-3 px-5 w-10">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          className="w-3.5 h-3.5 rounded border-zen-border bg-zen-surface text-zen-primary cursor-pointer"
                        />
                      </th>
                      <th className="py-3 px-3">Instance</th>
                      <th className="py-3 px-3">Part No.</th>
                      <th className="py-3 px-3">Description</th>
                      <th className="py-3 px-3 hidden lg:table-cell">Size</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zen-border/50">
                    {filteredItems.map(item => {
                      const key = rowKey(item)
                      const selected = selectedIds.has(key)
                      return (
                        <tr
                          key={key}
                          onClick={() => toggleSelection(key)}
                          className={`cursor-pointer transition-colors hover:bg-zen-surface-alt ${selected ? 'bg-zen-info/[0.04]' : ''}`}
                        >
                          <td className="py-3 px-5">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => {}}
                              className="w-3.5 h-3.5 rounded border-zen-border bg-zen-surface text-zen-primary cursor-pointer"
                            />
                          </td>
                          <td className="py-3 px-3">
                            <span className="text-sm font-medium text-zen-text-main">{item.instanceName || item.instance_name || '—'}</span>
                          </td>
                          <td className="py-3 px-3">
                            <span className="font-mono text-[11px] text-zen-text-dim">{item.partNumber || item.part_number || '—'}</span>
                          </td>
                          <td className="py-3 px-3">
                            <span className="text-xs text-zen-text-muted truncate max-w-[180px] block">{item.description || '—'}</span>
                          </td>
                          <td className="py-3 px-3 hidden lg:table-cell">
                            <span className="font-mono text-[10px] text-zen-text-muted">{item.millingSize || item.size || '—'}</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => generateViews(false)}
                disabled={loading || !isConnected || !hasSelection}
                className="zen-pill px-8 py-3 text-sm disabled:opacity-30 disabled:cursor-not-allowed disabled:transform-none flex items-center gap-2"
              >
                {loading
                  ? <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg>
                  : <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                }
                Generate Selected Views
              </button>

              <button
                onClick={() => generateViews(true)}
                disabled={loading || !isConnected || !hasSelection}
                title="Use the axis system currently selected/picked in CATIA's spec tree for all parts"
                className="px-6 py-3 bg-zen-success/10 hover:bg-zen-success/20 disabled:opacity-30 disabled:cursor-not-allowed text-zen-success border border-zen-success/20 rounded-full font-bold text-sm transition-all active:scale-95"
              >
                Generate (Axis from Selection)
              </button>

              {feedback && (
                <div className={`flex-1 min-w-0 px-4 py-2 rounded-xl text-xs font-mono border truncate ${feedback.startsWith('✓') ? 'bg-zen-success/5 border-zen-success/20 text-zen-success' : feedback.startsWith('Failed') || feedback.startsWith('Request') ? 'bg-zen-error/5 border-zen-error/20 text-zen-error' : 'bg-zen-info/5 border-zen-info/20 text-zen-info'}`}>
                  {feedback}
                </div>
              )}
            </div>
          </div>

          {/* Settings sidebar — 1 col */}
          <div className="space-y-4">
            <h3 className="zen-label">Settings</h3>

            <div className="zen-card border border-zen-border p-5 space-y-5">
              <div className="space-y-2">
                <label className="zen-label">Global Axis Name</label>
                <input
                  type="text"
                  value={axisName}
                  onChange={e => setAxisName(e.target.value)}
                  placeholder="Optional — leave blank for auto"
                  className="w-full bg-zen-surface-alt border border-zen-border rounded-lg px-3 py-2 text-xs text-zen-text-main focus:border-zen-info/50 outline-none transition-all"
                />
                <p className="text-[9px] text-zen-text-muted leading-relaxed">If blank, each part's own axis system is used automatically.</p>
              </div>

              <div className="space-y-2">
                <label className="zen-label">Top View Rotation</label>
                <select
                  value={rotation}
                  onChange={e => setRotation(Number(e.target.value))}
                  className="w-full appearance-none bg-zen-surface-alt border border-zen-border rounded-lg px-3 py-2 text-xs text-zen-text-main focus:border-zen-info/50 outline-none transition-all cursor-pointer"
                >
                  <option value={-90}>-90° (Plan View — default)</option>
                  <option value={0}>0°</option>
                  <option value={90}>90°</option>
                  <option value={180}>180°</option>
                </select>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zen-warning/5 border border-zen-warning/10">
              <p className="text-[10px] text-zen-warning/70 leading-relaxed">
                <strong className="text-zen-warning">Tip:</strong> For best results, ensure CATIA has the assembly open with all part documents loaded before generating.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
