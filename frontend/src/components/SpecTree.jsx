import { useState } from 'react'

export default function SpecTree({ treeData, onRefresh, taggedNode, onNodeTag }) {
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [expandedNodes, setExpandedNodes] = useState(new Set())

    const handleRefresh = async () => {
        setIsRefreshing(true)
        await onRefresh()
        setTimeout(() => setIsRefreshing(false), 500)
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
                    className={`spec-tree-node group cursor-pointer transition-colors ${isTagged ? 'bg-white/10 text-white' : 'hover:bg-white/5'}`}
                    style={{ paddingLeft: `${depth * 12 + 8}px` }}
                    onClick={() => onNodeTag(node)}
                >
                    <span 
                        className={`text-muted-foreground/60 p-1 hover:text-white transition-transform ${isExpanded ? 'rotate-0' : '-rotate-90'}`}
                        onClick={(e) => hasChildren ? toggleNode(nodeId, e) : null}
                    >
                        {hasChildren ? '▼' : '•'}
                    </span>
                    <span className={`font-semibold ${isTagged ? 'text-white' : 'text-foreground/90'}`}>{node.name}</span>
                    {node.type && (
                        <span className={`text-[9px] px-1 rounded uppercase ${isTagged ? 'bg-white/20 text-white' : 'text-muted-foreground/40 bg-white/5'}`}>
                            {node.type}
                        </span>
                    )}
                    {isTagged && (
                        <span className="ml-auto mr-2 text-[8px] uppercase tracking-tighter text-blue-400 font-bold">Tagged</span>
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
        <aside className="w-80 border-r border-white/5 flex flex-col bg-card/30 shrink-0">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
                <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Specification Tree</h2>
                <button
                    onClick={handleRefresh}
                    className={`text-muted-foreground hover:text-white transition-all ${isRefreshing ? 'animate-spin' : ''}`}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                    </svg>
                </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 font-mono text-[11px] selection:bg-white/10">
                {!treeData || Object.keys(treeData).length === 0 ? (
                    <div className="p-4 text-muted-foreground italic leading-relaxed">
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
