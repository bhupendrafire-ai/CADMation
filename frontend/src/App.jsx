import { useState, useEffect, useRef } from 'react'
import './App.css'
import ChatWindow from './components/ChatWindow'
import SpecTree from './components/SpecTree'
import StatusIndicator from './components/StatusIndicator'
import ChatSidebar from './components/ChatSidebar'

function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [activeDoc, setActiveDoc] = useState(null)
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Ready to assist with your CATIA V5 sheet metal die design. What would you like to build today?' }
  ])

  const [treeData, setTreeData] = useState(null)
  const [taggedNode, setTaggedNode] = useState(null)
  
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
    </div>
  )
}

export default App
