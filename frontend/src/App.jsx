import { useState, useEffect, useRef } from 'react'
import './App.css'
import ChatWindow from './components/ChatWindow'
import SpecTree from './components/SpecTree'
import StatusIndicator from './components/StatusIndicator'
import ChatSidebar from './components/ChatSidebar'
import { measureBomItems } from './utils/bomMeasurement'

function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [activeDoc, setActiveDoc] = useState(null)
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Ready to assist with your CATIA V5 sheet metal die design. What would you like to build today?' }
  ])

  const [treeData, setTreeData] = useState(null)
  const [taggedNode, setTaggedNode] = useState(null)
  const [pendingAxisWs, setPendingAxisWs] = useState(null)
  
  // Session / History Management
  const [sessionId, setSessionId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  
  const chatWindowRef = useRef(null)

  // Poll for CATIA connection status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch('/api/catia/status')
        const data = await res.json()
        setIsConnected(data.connected)
        setActiveDoc(data.active_document)
      } catch (err) {
        setIsConnected(false)
        setActiveDoc(null)
      }
    }

    checkStatus()
    const interval = setInterval(checkStatus, 5000)
    
    // History initialization
    refreshSessions()
    startNewSession()
    
    return () => clearInterval(interval)
  }, [])

  const refreshSessions = async () => {
    try {
      const res = await fetch('/api/chat/sessions')
      const data = await res.json()
      setSessions(data)
    } catch (err) {
      console.error("Failed to fetch sessions:", err)
    }
  }

  const startNewSession = async () => {
    try {
      const res = await fetch('/api/chat/sessions/new', { method: 'POST' })
      const data = await res.json()
      setSessionId(data.session_id)
      setMessages([
        { role: 'ai', content: 'Ready to assist with your CATIA V5 sheet metal die design. What would you like to build today?' }
      ])
    } catch (err) {
      console.error("Failed to create new session:", err)
    }
  }

  const handleSelectSession = async (id) => {
    try {
      const res = await fetch(`/api/chat/sessions/${id}`)
      const data = await res.json()
      setSessionId(data.id)
      setMessages(data.messages || [])
    } catch (err) {
      console.error("Failed to load session:", err)
    }
  }

  // Autosave messages to backend whenever they change
  useEffect(() => {
    if (!sessionId || messages.length <= 1) return // Skip initial or empty

    const timer = setTimeout(async () => {
      try {
        await fetch(`/api/chat/sessions/${sessionId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            messages,
            last_doc: activeDoc
          })
        })
        refreshSessions()
      } catch (err) {
        console.error("Autosave failed:", err)
      }
    }, 1000)

    return () => clearTimeout(timer)
  }, [messages, sessionId, activeDoc])

  const handleMeasurementAction = (action, data, ws) => {
    if (action === 'REQUIRE_AXIS_SELECTION') {
      setPendingAxisWs({ ws, log: data.log });
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: data.log || 'Please select the AP_AXIS in CATIA and click confirm.',
          interactive: {
            type: 'choice',
            options: [
              {
                id: 'confirm-axis',
                label: 'Confirm Axis Selected',
                primary: true,
                action: {
                  type: 'send-ws-command',
                  ws: ws, // Internal ref
                  command: 'AXIS_CONFIRMED'
                },
              }
            ],
          },
        },
      ])
    }

    if (action === 'REQUIRE_BODY_SELECTION') {
      // Body selection is handled in-place by BOMSelectionList now.
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: `Multiple bodies detected for ${data.itemId}. Choose the correct one in the measurement window.`
        }
      ]);
    }
  }

  const handleSendMessage = async (content) => {
    // Add user message immediately
    const userMsg = { role: 'user', content }
    setMessages(prev => [...prev, userMsg])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: content,
          session_id: sessionId,
          history: messages,
          tagged_node: taggedNode
        })
      })

      const data = await res.json()
      
      // Update with AI reply and output context
      const aiMsg = { 
        role: 'ai', 
        content: data.reply + 
                 (data.output ? `\n\n**Execution Log:**\n\`\`\`\n${data.output}\n\`\`\`` : "") +
                 (data.executed ? "\n\n✅ Changes applied to CATIA." : (data.error ? `\n\n❌ Error: ${data.error}` : "")),
        interactive: data.interactive
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: "Sorry, I'm having trouble connecting to the backend." }])
    } finally {
      refreshSessions()
    }
  }

  const handleRefreshTree = async () => {
    if (!isConnected) return
    try {
      const res = await fetch('/api/catia/tree')
      const data = await res.json()
      if (!data.error) {
        setTreeData(data)
      }
    } catch (err) {
      console.error("Failed to refresh tree:", err)
    }
  }

  const handleNodeTag = (node) => {
    setTaggedNode(node)
    if (node && chatWindowRef.current) {
      chatWindowRef.current.insertText(node.name)
    }
  }

  const handleGenerateBOM = (items, error) => {
    if (error) {
      setMessages((prev) => [...prev, { role: 'ai', content: `BOM failed: ${error}` }])
      return
    }
    if (!items || !items.length) {
      setMessages((prev) => [...prev, { role: 'ai', content: 'No BOM items found. Open a CATIA assembly and refresh the tree.' }])
      return
    }
    setMessages((prev) => [
      ...prev,
      {
        role: 'ai',
        content: 'I have scanned the active document (ignoring hidden items). Please select the items you wish to measure for the BOM:',
        interactive: {
          type: 'bom-selector',
          items: items
        },
      },
    ])
  }

  const mergeBomResults = (existingItems, retryResults) => {
    const retryByKey = new Map(
      (retryResults || []).map((row) => [`${row.partNumber}|${row.instanceName}`, row])
    )
    return (existingItems || []).map((row) => {
      const key = `${row.partNumber}|${row.instanceName}`
      return retryByKey.has(key) ? { ...row, ...retryByKey.get(key) } : row
    })
  }

  const handleBomSelectionComplete = async (messageIndex, payload) => {
    const requestedItems = payload?.items || []
    const method = payload?.method || 'ROUGH_STOCK'

    if (payload?.results) {
       // Results already provided by the selector component
       handleUpdateBomMessage(messageIndex, {
         items: payload.results,
         exporting: false,
       })
       return;
    }

    handleUpdateBomMessage(messageIndex, {
      items: (payload?.items || []).map(it => ({ ...it, stock_size: 'Measuring...' })),
      exporting: false,
    })

    try {
      const data = await measureBomItems({
        items: requestedItems,
        method: method,
        onLog: (log) => {
          handleUpdateBomMessage(messageIndex, { 
             log: log // Assuming the component collects these
          })
        },
        onAction: handleMeasurementAction
      })

      handleUpdateBomMessage(messageIndex, {
        items: data.results || [],
        exporting: false,
      })
      
      // Handle retries if any items failed Rough Stock
      const retryCandidates = (data.results || []).filter(r => 
        r.method_used === 'ROUGH_STOCK' && (r.stock_size.includes('Not') || r.stock_size.includes('Error'))
      )

      if (retryCandidates.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: `${retryCandidates.length} item(s) failed Rough Stock. Retry with STL?`,
            interactive: {
              type: 'choice',
              options: [
                {
                  id: 'retry-stl',
                  label: 'Retry failed items with STL',
                  primary: true,
                  action: {
                    type: 'retry-bom-failures-stl',
                    targetMessageIndex: messageIndex,
                    items: retryCandidates,
                  },
                }
              ]
            }
          }
        ])
      }
    } catch (err) {
       setMessages(prev => [...prev, { role: 'ai', content: `Measurement failed: ${err.message}` }])
    }
  }

  const handleInteractiveAction = async (_messageIndex, action) => {
    if (!action?.type) return

    if (action.type === 'send-ws-command') {
       if (action.ws && action.ws.readyState === WebSocket.OPEN) {
         action.ws.send(JSON.stringify({ 
           command: action.command,
           bodyName: action.bodyName
        }));
        setMessages(prev => [...prev, { 
          role: 'ai', 
          content: action.command === 'AXIS_CONFIRMED' 
            ? '✅ Axis selection confirmed. Resuming measurement...' 
            : `✅ ${action.bodyName} selected. Resuming measurement...` 
        }]);
       }
       return;
    }

    if (action.type === 'dismiss-bom-failure-retry') {
      setMessages((prev) => [...prev, { role: 'ai', content: 'STL retry skipped. Current BOM results are unchanged.' }])
      return
    }

    if (action.type === 'retry-bom-failures-stl') {
      setMessages((prev) => [...prev, { role: 'ai', content: 'Retrying failed BOM items with STL...' }])
      try {
        const data = await measureBomItems({
          items: action.items || [],
          method: 'STL',
          onAction: handleMeasurementAction
        })
        setMessages((prev) => {
          const next = [...prev]
          const targetMsg = next[action.targetMessageIndex]
          if (targetMsg?.bomEditor) {
            next[action.targetMessageIndex] = {
              ...targetMsg,
              bomEditor: {
                ...targetMsg.bomEditor,
                items: mergeBomResults(targetMsg.bomEditor.items, data.results || []),
              },
            }
          }
          return next
        })
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: `STL retry completed for ${action.items?.length || 0} item(s).` },
        ])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: `STL retry failed: ${err.message}` },
        ])
      }
    }
  }

  const handleUpdateBomMessage = (messageIndex, bomData) => {
    setMessages((prev) =>
      prev.map((m, i) => {
        if (i === messageIndex) {
          // If we are transitioning from selector to editor, clear interactive type
          const nextMsg = { ...m, bomEditor: bomData };
          if (nextMsg.interactive?.type === 'bom-selector') {
             nextMsg.interactive = null;
          }
          return nextMsg;
        }
        return m;
      })
    )
  }

  const handleBomExport = async (messageIndex, items) => {
    const msg = messages[messageIndex]
    if (msg?.bomEditor) {
      setMessages((prev) =>
        prev.map((m, i) =>
          i === messageIndex ? { ...m, bomEditor: { ...m.bomEditor, exporting: true } } : m
        )
      )
    }
    try {
      const res = await fetch('/api/catia/bom/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: `BOM exported to:\n${data.file_path}` },
        ])
      } else {
        setMessages((prev) => [...prev, { role: 'ai', content: `Export failed: ${data.error}` }])
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'ai', content: 'Failed to connect for BOM export.' }])
    } finally {
      if (msg?.bomEditor) {
        setMessages((prev) =>
          prev.map((m, i) =>
            i === messageIndex ? { ...m, bomEditor: { ...m.bomEditor, exporting: false } } : m
          )
        )
      }
    }
  }

  // Initial tree fetch when connected
  useEffect(() => {
    if (isConnected) {
      handleRefreshTree()
    } else {
      setTreeData(null)
    }
  }, [isConnected])

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Header */}
      <header className="h-14 border-b border-white/5 flex items-center px-6 justify-between shrink-0 glass z-10">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-white rounded-sm rotate-45 flex items-center justify-center">
            <div className="w-3 h-3 bg-black rounded-full"></div>
          </div>
          <h1 className="text-sm font-bold tracking-widest uppercase">CADMation</h1>
          <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded-full text-muted-foreground font-mono">V0.1.0</span>
        </div>

        <StatusIndicator isConnected={isConnected} />
      </header>

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden">
        <SpecTree
          treeData={treeData}
          onRefresh={handleRefreshTree}
          taggedNode={taggedNode}
          onNodeTag={handleNodeTag}
          onGenerateBOM={handleGenerateBOM}
        />

        <ChatWindow
          ref={chatWindowRef}
          messages={messages}
          onSendMessage={handleSendMessage}
          onUpdateBomMessage={handleUpdateBomMessage}
          onBomExport={handleBomExport}
          onInteractiveAction={handleInteractiveAction}
          onMeasurementAction={handleMeasurementAction}
          onBomSelectionComplete={handleBomSelectionComplete}
        />

        <ChatSidebar
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
          sessions={sessions}
          currentSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={startNewSession}
        />
      </main>

      {/* Connection Toggle (Hidden/Dev only) */}
      <button
        onClick={() => setIsConnected(!isConnected)}
        className="fixed bottom-4 right-4 text-[9px] text-white/10 hover:text-white/40 transition-colors uppercase font-mono"
      >
        Toggle Dev Connection
      </button>

      {/* Interactive Axis Selection Modal */}
      {pendingAxisWs && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-xl animate-in fade-in duration-300">
          <div className="glass p-10 rounded-[2rem] border border-white/10 max-w-lg w-full shadow-2xl shadow-blue-500/10 animate-in zoom-in-95 slide-in-from-bottom-5 duration-500">
             <div className="flex items-center gap-4 mb-8">
                <div className="w-12 h-12 bg-blue-500/20 rounded-2xl flex items-center justify-center">
                   <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
                </div>
                <div>
                   <h2 className="text-2xl font-bold tracking-tight">Manual Action Required</h2>
                   <p className="text-blue-400 text-xs font-mono uppercase tracking-widest mt-1">CATIA V5 Interaction</p>
                </div>
             </div>
             
             <div className="bg-white/5 rounded-2xl p-6 mb-8 border border-white/5">
                <p className="text-sm text-neutral-300 leading-relaxed font-medium">
                   {pendingAxisWs.log}
                </p>
             </div>

             <div className="flex flex-col gap-3">
                <button
                  onClick={() => {
                    if (pendingAxisWs.ws && pendingAxisWs.ws.readyState === WebSocket.OPEN) {
                      pendingAxisWs.ws.send(JSON.stringify({ command: 'AXIS_CONFIRMED' }));
                    }
                    setMessages(prev => [...prev, { role: 'ai', content: '✅ Axis selection confirmed. Resuming measurement...' }]);
                    setPendingAxisWs(null);
                  }}
                  className="w-full h-14 bg-white text-black rounded-2xl font-bold hover:bg-neutral-200 active:scale-[0.98] transition-all shadow-xl shadow-white/5"
                >
                   I have selected the Axis
                </button>
                <p className="text-[10px] text-center text-neutral-500 uppercase tracking-widest font-bold">
                   Resuming automation after confirmation
                </p>
             </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
