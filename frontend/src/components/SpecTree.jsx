import { useState } from 'react'

export default function SpecTree({ treeData, onRefresh, taggedNode, onNodeTag, onGenerateBOM }) {
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [isGeneratingBOM, setIsGeneratingBOM] = useState(false)
    const [expandedNodes, setExpandedNodes] = useState(new Set())
    const [bomModalOpen, setBomModalOpen] = useState(false)
    const [tempRenameDuplicateBodies, setTempRenameDuplicateBodies] = useState(false)
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

    const handleRefresh = async () => {
        setIsRefreshing(true)
        await onRefresh()
        setTimeout(() => setIsRefreshing(false), 500)
    }

    const openBomModal = () => {
        if (!treeData) return
        setTempRenameDuplicateBodies(false)
        setBomModalOpen(true)
    }

    const cancelBomModal = () => {
        setBomModalOpen(false)
    }

    const confirmBomModal = async () => {
        setBomModalOpen(false)
        const opts = { tempRenameDuplicateBodies }
        if (!treeData) return
        setIsGeneratingBOM(true)
        try {
            const res = await fetch('/api/catia/bom/fast')
            const data = await res.json()
            if (data.error) {
                onGenerateBOM?.([], data.error, opts)
                return
            }
            onGenerateBOM?.(data.items || [], null, opts)
        } catch (err) {
            console.error("Failed to load BOM items:", err)
            onGenerateBOM?.([], err?.message || "Network error", opts)
        } finally {
            setIsGeneratingBOM(false)
        }
    }

    const toggleNode = (nodeId, e) => {
        e.stopPropagation()
        setExpandedNodes(prev => {
            const next = new Set(prev)
            if (next.has(nodeId)) next.delete(nodeId)
            else next.add(nodeId)
            return next
        })
    }

    const renderNode = (node, depth = 0, path = '') => {
        if (!node) return null

        const nodeId = path ? `${path}/${node.name}` : node.name
        const isExpanded = expandedNodes.has(nodeId)
        const hasChildren = node.children && node.children.length > 0
        const isTagged = taggedNode?.name === node.name && taggedNode?.type === node.type

        return (
            <div key={nodeId} className="flex flex-col">
                <div 
                    className={`spec-tree-node group cursor-pointer transition-colors ${isTagged ? 'bg-zen-primary/[0.06] text-zen-text-main' : ''}`}
                    style={{ paddingLeft: `${depth * 12 + 8}px` }}
                    onClick={() => onNodeTag(node)}
                >
                    <span 
                        className={`text-zen-text-muted p-1 hover:text-zen-text-main transition-transform ${isExpanded ? 'rotate-0' : '-rotate-90'}`}
                        onClick={(e) => hasChildren ? toggleNode(nodeId, e) : null}
                    >
                        {hasChildren ? '▼' : '•'}
                    </span>
                    <span className={`font-semibold ${isTagged ? 'text-zen-primary' : 'text-zen-text-main'}`}>{node.name}</span>
                    {node.type && (
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-md uppercase ${isTagged ? 'bg-zen-primary/10 text-zen-primary' : 'text-zen-text-muted bg-zen-surface-alt'}`}>
                            {node.type}
                        </span>
                    )}
                    {isTagged && (
                        <span className="ml-auto mr-2 text-[8px] uppercase tracking-tighter text-zen-info font-bold">Tagged</span>
                    )}
                </div>
                {hasChildren && isExpanded && (
                    <div className="flex flex-col">
                        {node.children.map(child => renderNode(child, depth + 1, nodeId))}
                    </div>
                )}
            </div>
        )
    }

    return (
        <aside
            className={`border-r border-zen-border flex flex-col bg-zen-surface shrink-0 transition-[width] duration-200 ease-out overflow-hidden ${
                sidebarCollapsed ? 'w-12' : 'w-80'
            }`}
            aria-label="Specification tree"
        >
            <div
                className={`border-b border-zen-border shrink-0 ${
                    sidebarCollapsed ? 'flex flex-col items-center gap-2 py-2 px-1' : 'p-4 flex items-center gap-2'
                }`}
            >
                <button
                    type="button"
                    onClick={() => setSidebarCollapsed((c) => !c)}
                    aria-pressed={sidebarCollapsed}
                    className="text-zen-text-muted hover:text-zen-text-main p-1.5 rounded-md hover:bg-zen-surface-alt shrink-0"
                    title={sidebarCollapsed ? 'Expand specification tree' : 'Collapse specification tree'}
                >
                    {sidebarCollapsed ? (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="m9 18 6-6-6-6" />
                        </svg>
                    ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="m15 18-6-6 6-6" />
                        </svg>
                    )}
                </button>
                {!sidebarCollapsed && (
                    <h2 className="zen-label flex-1 min-w-0 truncate">
                        Specification Tree
                    </h2>
                )}
                <div className={`flex items-center gap-2 ${sidebarCollapsed ? 'flex-col' : 'ml-auto'}`}>
                    <button
                        onClick={openBomModal}
                        disabled={isGeneratingBOM || !treeData}
                        className={`group relative flex items-center justify-center p-1.5 rounded-md transition-all ${isGeneratingBOM ? 'bg-zen-surface-alt cursor-wait' : 'hover:bg-zen-surface-alt text-zen-text-muted hover:text-zen-text-main active:scale-95'}`}
                        title="Generate Excel BOM"
                    >
                        {isGeneratingBOM ? (
                            <div className="w-3.5 h-3.5 border-2 border-zen-border border-t-zen-primary rounded-full animate-spin" />
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect width="8" height="4" x="8" y="2" rx="1" ry="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M9 12h6" /><path d="M9 16h6" /><path d="M9 8h6" />
                            </svg>
                        )}
                    </button>
                    <button
                        onClick={handleRefresh}
                        className={`text-zen-text-muted hover:text-zen-text-main transition-all p-1.5 rounded-md hover:bg-zen-surface-alt ${isRefreshing ? 'animate-spin' : ''}`}
                        title="Refresh Tree"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                        </svg>
                    </button>
                </div>
            </div>
            {bomModalOpen && (
                <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/20 backdrop-blur-sm p-4">
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="bom-opt-title"
                        className="zen-card w-full max-w-md border border-zen-border p-5"
                    >
                        <h2 id="bom-opt-title" className="text-sm font-bold text-zen-text-main mb-2">
                            BOM measurement options
                        </h2>
                        <p className="text-[11px] text-zen-text-dim leading-relaxed mb-4">
                            Duplicate PartDesign body names (e.g. several <span className="font-mono text-zen-text-main">MAIN_BODY</span>)
                            can confuse Rough Stock Search. You can optionally assign temporary unique names
                            (<span className="font-mono text-zen-text-main">MAIN_BODY__CADM0</span>, …) for this measure run only.
                            CADMation does not save your CATPart; CATIA may show the document as modified until names are restored
                            at the end of the run. If restore fails, close without saving or undo.
                        </p>
                        <label className="flex items-start gap-3 cursor-pointer mb-5">
                            <input
                                type="checkbox"
                                checked={tempRenameDuplicateBodies}
                                onChange={(e) => setTempRenameDuplicateBodies(e.target.checked)}
                                className="mt-0.5 rounded border-zen-border"
                            />
                            <span className="text-xs text-zen-text-main">
                                Rename duplicate bodies in CATIA (__CADM0, __CADM1, …) for BOM measurement
                            </span>
                        </label>
                        <div className="flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={cancelBomModal}
                                className="px-4 py-2 text-xs rounded-full border border-zen-border text-zen-text-dim hover:bg-zen-surface-alt transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={confirmBomModal}
                                className="zen-pill px-4 py-2 text-xs"
                            >
                                Continue
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div
                className={`flex-1 overflow-y-auto p-2 font-mono text-[11px] selection:bg-zen-info/10 min-h-0 ${
                    sidebarCollapsed ? 'hidden' : ''
                }`}
            >
                {!treeData || Object.keys(treeData).length === 0 ? (
                    <div className="p-4 text-zen-text-muted italic leading-relaxed">
                        No active document detected.
                        <br />
                        Connect to CATIA to view the specification tree.
                    </div>
                ) : (
                    <div className="py-2">
                        {renderNode(treeData)}
                    </div>
                )}
            </div>
        </aside>
    )
}
