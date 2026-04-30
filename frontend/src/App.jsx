import { useState, useEffect, useRef } from 'react'
import './App.css'
import ChatWindow from './components/ChatWindow'
import SpecTree from './components/SpecTree'
import StatusIndicator from './components/StatusIndicator'
import ChatSidebar from './components/ChatSidebar'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import DraftingPage from './components/DraftingPage'
import BOMEditor from './components/BOMEditor'
import BOMSelectionList from './components/BOMSelectionList'
import HowToUseModal from './components/HowToUseModal'
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
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isCopilotOpen, setIsCopilotOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(true)
  const [exportStatus, setExportStatus] = useState({ 
    status: 'idle', 
    path: '', 
    error: '' 
  })
  const [showGuide, setShowGuide] = useState(() => {
    return localStorage.getItem('cadmation_hide_guide') !== 'true'
  })
  
  const chatWindowRef = useRef(null)
  const messagesRef = useRef(messages)
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

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

  const handleGenerateBOM = (items, error, options = {}) => {
    if (error) {
      setMessages((prev) => [...prev, { role: 'ai', content: `BOM failed: ${error}` }])
      return
    }
    if (!items || !items.length) {
      setMessages((prev) => [...prev, { role: 'ai', content: 'No BOM items found. Open a CATIA assembly and refresh the tree.' }])
      return
    }
    const bomOptions = {
      tempRenameDuplicateBodies: !!options?.tempRenameDuplicateBodies,
    }
    setMessages((prev) => [
      ...prev,
      {
        id: `bom-${Date.now()}`,
        role: 'ai',
        content: 'I have scanned the active document (ignoring hidden items). Please select the items you wish to measure for the BOM:',
        interactive: {
          type: 'bom-selector',
          items: items,
          bomOptions,
        },
      },
    ])
    setActiveTab('bom')
    setIsCopilotOpen(true)
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
      const bomOpts = messagesRef.current[messageIndex]?.interactive?.bomOptions
      const data = await measureBomItems({
        items: requestedItems,
        projectName: activeDoc,
        method: method,
        tempRenameDuplicateBodies: !!bomOpts?.tempRenameDuplicateBodies,
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
          projectName: activeDoc,
          method: 'STL',
          onAction: handleMeasurementAction
        })
        let mergedItems = []
        setMessages((prev) => {
          const next = [...prev]
          const targetMsg = next[action.targetMessageIndex]
          if (targetMsg?.bomEditor) {
            mergedItems = mergeBomResults(targetMsg.bomEditor.items, data.results || [])
            next[action.targetMessageIndex] = {
              ...targetMsg,
              bomEditor: {
                ...targetMsg.bomEditor,
                items: mergedItems,
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

  const handleBomDraftUpdate = (messageIndex, items) => {
    setMessages((prev) => {
      const msg = prev[messageIndex];
      if (!msg || !msg.interactive || msg.interactive.type !== 'bom-selector') {
        return prev;
      }
      
      const currentItemsJson = JSON.stringify(msg.interactive.items);
      const nextItemsJson = JSON.stringify(items);
      if (currentItemsJson === nextItemsJson) return prev;

      return prev.map((m, i) => 
        i === messageIndex ? { ...m, interactive: { ...m.interactive, items } } : m
      );
    });
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
    const msg = messageIndex !== null ? messages[messageIndex] : null
    
    setExportStatus({ status: 'exporting', path: '', error: '' })

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
        setExportStatus({ status: 'success', path: data.file_path, error: '' })
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: `BOM exported to:\n${data.file_path}` },
        ])
      } else {
        const err = data.error || 'Export failed'
        setExportStatus({ status: 'error', path: '', error: err })
        setMessages((prev) => [...prev, { role: 'ai', content: `Export failed: ${err}` }])
      }
    } catch (err) {
      setExportStatus({ status: 'error', path: '', error: 'Failed to connect for BOM export.' })
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

  const handleOpenFile = async (path) => {
    try {
      const res = await fetch('/api/catia/bom/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      const data = await res.json()
      if (!res.ok || data.error) {
        alert(`Failed to open file: ${data.error || 'Unknown error'}`)
      }
    } catch (err) {
      alert(`Request failed: ${err.message}`)
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

  const lastBomMsg = [...messages].reverse().find(m => m.bomEditor || (m.interactive && m.interactive.type === 'bom-selector'))
  const stats = {
    totalItems: treeData?.node_count || 0,
    pendingReviews: messages.filter(m => m.bomEditor?.items?.some(it => it.reviewStatus === 'needs_review')).length,
    readyForExport: messages.filter(m => m.bomEditor?.items?.length > 0).length,
    activeDrafts: sessions.length
  }

  const renderActiveWorkspace = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard stats={stats} onNavigate={setActiveTab} />
      case 'tree':
        return (
          <div className="flex-1 flex overflow-hidden">
             <SpecTree
               treeData={treeData}
               onRefresh={handleRefreshTree}
               taggedNode={taggedNode}
               onNodeTag={handleNodeTag}
               onGenerateBOM={(items, err, opts) => {
                 handleGenerateBOM(items, err, opts)
                 setActiveTab('bom')
                 setIsCopilotOpen(true)
               }}
             />
              <div className="flex-1 bg-zen-surface-alt flex items-center justify-center text-zen-text-muted">
                <div className="text-center">
                  <svg className="w-16 h-16 mx-auto mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"></path></svg>
                   <p className="text-sm font-medium uppercase tracking-widest text-zen-text-muted">Select a node to inspect properties</p>
                </div>
             </div>
          </div>
        )
      case 'bom':
        if (lastBomMsg) {
          const i = messages.indexOf(lastBomMsg)
          return (
            <div className="flex-1 overflow-hidden p-6 bg-zen-bg">
              {lastBomMsg.bomEditor && (
                <BOMEditor
                  items={lastBomMsg.bomEditor.items}
                  projectName={activeDoc}
                  onItemsChange={(items) => handleUpdateBomMessage?.(i, { ...lastBomMsg.bomEditor, items })}
                  onExport={(items) => handleBomExport?.(i, items)}
                  disabled={lastBomMsg.bomEditor.exporting}
                  isFullscreen={true}
                />
              )}
              {lastBomMsg.interactive && lastBomMsg.interactive.type === 'bom-selector' && (
                <div className="max-w-6xl mx-auto">
                  <BOMSelectionList
                    key={lastBomMsg.id || messages.indexOf(lastBomMsg)}
                    items={lastBomMsg.interactive.items}
                    projectName={activeDoc}
                    bomOptions={lastBomMsg.interactive.bomOptions}
                    onAction={handleMeasurementAction}
                    onUpdate={(items) => handleBomDraftUpdate?.(i, items)}
                    onCalculationComplete={(payload) => {
                      handleBomSelectionComplete?.(i, payload)
                    }}
                    onPartialExport={(items) => handleBomExport?.(i, items)}
                  />
                </div>
              )}
            </div>
          )
        }
        return (
          <div className="flex-1 flex flex-col items-center justify-center text-zen-text-muted p-10">
            <svg className="w-20 h-20 mb-6 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            <h3 className="text-lg font-bold text-zen-text-dim mb-2">No Active BOM</h3>
            <p className="text-sm text-center max-w-md">Go to the Assembly Tree to scan your CATIA project and generate a new Bill of Materials.</p>
            <button onClick={() => setActiveTab('tree')} className="zen-pill mt-8 px-8 py-3 text-sm">Go to Assembly Tree</button>
          </div>
        )
      case 'drafting':
        return (
          <DraftingPage activeDoc={activeDoc} isConnected={isConnected} lastBomMsg={lastBomMsg} />
        )
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zen-bg text-zen-text-main font-sans antialiased">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <Header isConnected={isConnected} activeDoc={activeDoc} />
        
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {renderActiveWorkspace()}
          
          {/* Copilot Drawer Trigger */}
          {!isCopilotOpen && (
            <button 
              onClick={() => setIsCopilotOpen(true)}
              className="fixed bottom-8 right-8 w-14 h-14 bg-zen-primary rounded-2xl flex items-center justify-center shadow-[0_16px_48px_-8px_rgba(26,26,26,0.3)] hover:scale-110 active:scale-95 transition-all z-50 group"
              title="Open Copilot"
            >
              <svg className="w-6 h-6 text-white group-hover:rotate-12 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-zen-error rounded-full border-2 border-zen-bg flex items-center justify-center">
                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
              </div>
            </button>
          )}

          {/* Copilot / Chat Drawer */}
          <div className={`fixed inset-y-0 right-0 w-[450px] bg-zen-surface border-l border-zen-border shadow-[−16px_0_48px_rgba(0,0,0,0.08)] transition-all duration-500 transform z-[60] flex flex-col ${isCopilotOpen ? 'translate-x-0' : 'translate-x-full'}`}>
            <div className="h-16 border-b border-zen-border flex items-center px-6 justify-between shrink-0 bg-zen-surface-alt">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 bg-zen-primary rounded-lg flex items-center justify-center">
                   <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                </div>
                <h3 className="text-sm font-bold text-zen-text-main">AI Copilot</h3>
              </div>
              <button 
                onClick={() => setIsCopilotOpen(false)}
                className="p-2 hover:bg-zen-surface-alt rounded-lg text-zen-text-muted hover:text-zen-text-main transition-all"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-hidden flex flex-col">
              <ChatWindow
                ref={chatWindowRef}
                messages={messages}
                activeDoc={activeDoc}
                onSendMessage={handleSendMessage}
                onUpdateBomMessage={handleUpdateBomMessage}
                onBomExport={handleBomExport}
                onInteractiveAction={handleInteractiveAction}
                onMeasurementAction={handleMeasurementAction}
                onBomSelectionComplete={handleBomSelectionComplete}
                onBomDraftUpdate={handleBomDraftUpdate}
                isEmbedded={true}
              />
            </div>

            <div className="p-4 bg-zen-surface-alt border-t border-zen-border">
              <ChatSidebar
                isOpen={isHistoryOpen}
                onToggle={() => setIsHistoryOpen(!isHistoryOpen)}
                sessions={sessions}
                currentSessionId={sessionId}
                onSelectSession={handleSelectSession}
                onNewChat={startNewSession}
                isCompact={true}
              />
            </div>
          </div>
        </main>
      </div>

      {showGuide && <HowToUseModal onClose={() => setShowGuide(false)} />}

      {pendingAxisWs && (
        <AxisSelectionModal
          isOpen={!!pendingAxisWs}
          onClose={() => setPendingAxisWs(null)}
          onConfirm={() => {
            if (pendingAxisWs.ws && pendingAxisWs.ws.readyState === WebSocket.OPEN) {
              pendingAxisWs.ws.send(JSON.stringify({ command: 'AXIS_CONFIRMED' }));
              setMessages(prev => [...prev, { 
                role: 'ai', 
                content: '✅ Axis selection confirmed. Resuming measurement...' 
              }]);
            }
            setPendingAxisWs(null);
          }}
          log={pendingAxisWs.log}
        />
      )}

      <ExportModal 
        state={exportStatus} 
        onClose={() => setExportStatus({ ...exportStatus, status: 'idle' })} 
        onOpenFile={handleOpenFile}
      />
    </div>
  )
}

function AxisSelectionModal({ isOpen, onClose, onConfirm, log }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm">
      <div className="zen-card w-full max-w-md border border-zen-border overflow-hidden">
        <div className="p-6">
          <div className="w-12 h-12 bg-zen-warning/10 rounded-full flex items-center justify-center mb-4 mx-auto">
            <svg className="w-6 h-6 text-zen-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="text-xl font-bold text-zen-text-main text-center mb-2">Axis Selection Required</h3>
          <p className="text-zen-text-dim text-sm text-center mb-6 leading-relaxed">
            {log || "Please select the 'AP_AXIS' Publication in CATIA before proceeding."}
          </p>
          
          <div className="flex flex-col gap-3">
            <button
              onClick={onConfirm}
              className="zen-pill w-full py-3 text-sm"
            >
              I have selected the Axis
            </button>
            <button
              onClick={onClose}
              className="w-full py-3 bg-zen-surface-alt text-zen-text-dim font-medium rounded-full hover:bg-zen-border transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ExportModal({ state, onClose, onOpenFile }) {
  if (state.status === 'idle') return null;

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-black/20 backdrop-blur-md animate-in">
      <div className="zen-card w-full max-w-md border border-zen-border overflow-hidden p-8 flex flex-col items-center text-center">
        
        {state.status === 'exporting' && (
          <>
            <div className="w-16 h-16 rounded-full border-2 border-zen-border border-t-zen-primary animate-spin mb-6"></div>
            <h3 className="text-xl font-bold text-zen-text-main mb-2">Generating Excel BOM</h3>
            <p className="text-zen-text-dim text-sm">Please wait while we compile your measurements and styles into a production-ready Excel sheet...</p>
          </>
        )}

        {state.status === 'success' && (
          <>
            <div className="w-16 h-16 bg-zen-success/10 rounded-full flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-zen-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-zen-text-main mb-2">Export Successful</h3>
            <div className="w-full bg-zen-surface-alt rounded-xl p-4 mb-6 border border-zen-border">
               <p className="zen-label text-left mb-1">Save Location</p>
               <p className="text-[11px] text-zen-success font-mono break-all text-left">{state.path}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 w-full">
              <button
                onClick={() => onOpenFile(state.path)}
                className="zen-pill py-3.5 text-sm flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                Open Excel
              </button>
              <button
                onClick={onClose}
                className="py-3.5 bg-zen-surface-alt text-zen-text-dim font-bold rounded-full hover:bg-zen-border transition-all"
              >
                Dismiss
              </button>
            </div>
          </>
        )}

        {state.status === 'error' && (
          <>
            <div className="w-16 h-16 bg-zen-error/10 rounded-full flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-zen-error" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-zen-text-main mb-2">Export Failed</h3>
            <p className="text-zen-error text-sm mb-8">{state.error}</p>
            <button
              onClick={onClose}
              className="zen-pill w-full py-4 text-sm"
            >
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default App
