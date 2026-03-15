import { useState, useEffect, useRef } from 'react'

export default function BOMSelectionList({ items: initialItems, onCalculationComplete }) {
    const [items, setItems] = useState(initialItems || [])
    const [calculating, setCalculating] = useState(false)
    const [progress, setProgress] = useState(0)
    const [logs, setLogs] = useState([])
    const [results, setResults] = useState(null)
    const wsRef = useRef(null)
    const logEndRef = useRef(null)

    useEffect(() => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [logs])

    const toggleItem = (id) => {
        setItems(prev => prev.map(item => 
            item.id === id ? { ...item, selected: !item.selected } : item
        ))
    }

    const selectAll = (selected) => {
        setItems(prev => prev.map(item => ({ ...item, selected })))
    }

    const startCalculation = () => {
        const selectedItems = items.filter(i => i.selected)
        if (selectedItems.length === 0) return

        setCalculating(true)
        setProgress(0)
        setLogs(['Connecting to measure engine...'])

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        const wsUrl = `${protocol}//${host}/api/catia/bom/calculate/ws`
        
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            setLogs(prev => [...prev, 'Starting measurement process...'])
            ws.send(JSON.stringify({ items: selectedItems }))
        }

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            if (data.progress !== undefined) setProgress(data.progress)
            if (data.log) setLogs(prev => [...prev, data.log])
            if (data.status === 'done') {
                setResults(data.results)
                setLogs(prev => [...prev, 'Done! Finalizing results...'])
                setTimeout(() => {
                    onCalculationComplete?.(data.results)
                }, 1000)
            }
            if (data.error) {
                setLogs(prev => [...prev, `Error: ${data.error}`])
                setCalculating(false)
            }
        }

        ws.onclose = () => {
            console.log('WS closed')
        }

        ws.onerror = (err) => {
            setLogs(prev => [...prev, 'Connection error.'])
            setCalculating(false)
        }
    }

    if (calculating) {
        return (
            <div className="mt-4 p-4 rounded-xl border border-white/10 bg-black/40 space-y-4">
                <div className="flex items-center justify-between text-xs font-medium text-white/50 mb-1">
                    <span className="truncate max-w-[80%]">{logs[logs.length - 1]}</span>
                    <span>{progress}%</span>
                </div>
                <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div 
                        className="h-full bg-white transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>
                <div className="text-[10px] text-white/40 font-mono h-32 overflow-y-auto bg-black/40 p-2 rounded border border-white/5 custom-scrollbar">
                    {logs.map((entry, i) => (
                        <div key={i} className="mb-0.5 leading-relaxed">
                            <span className="opacity-30 mr-2">[{new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})}]</span>
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
                <span className="text-xs font-semibold text-white/70">Select Items to Measure</span>
                <div className="flex gap-2">
                    <button onClick={() => selectAll(true)} className="text-[10px] text-white/40 hover:text-white transition-colors">Select All</button>
                    <span className="text-white/10">|</span>
                    <button onClick={() => selectAll(false)} className="text-[10px] text-white/40 hover:text-white transition-colors">None</button>
                </div>
            </div>
            
            <div className="max-h-60 overflow-y-auto p-2 space-y-1">
                {items.map((item, idx) => (
                    <div 
                        key={`${item.id}-${idx}`} 
                        onClick={() => toggleItem(item.id)}
                        className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${item.selected ? 'bg-white/10 text-white' : 'text-white/40 hover:bg-white/5'}`}
                    >
                        <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${item.selected ? 'bg-white border-white' : 'border-white/20'}`}>
                            {item.selected && (
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12" />
                                </svg>
                            )}
                        </div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-xs font-semibold truncate text-white/90">{item.instanceName}</span>
                            <span className="text-[10px] font-mono opacity-50 truncate">{item.name}</span>
                        </div>
                        {item.qty > 1 && (
                            <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-white/60 shrink-0">
                                x{item.qty}
                            </span>
                        )}
                        <span className="ml-auto text-[10px] opacity-50 uppercase tracking-tighter">{item.type}</span>
                    </div>
                ))}
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
