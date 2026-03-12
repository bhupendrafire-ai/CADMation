import { useState, useEffect, useRef } from 'react'
import './App.css'
import ChatWindow from './components/ChatWindow'
import SpecTree from './components/SpecTree'
import StatusIndicator from './components/StatusIndicator'

function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [activeDoc, setActiveDoc] = useState(null)
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Ready to assist with your CATIA V5 sheet metal die design. What would you like to build today?' }
  ])

  const [treeData, setTreeData] = useState(null)
  const [taggedNode, setTaggedNode] = useState(null)
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
    return () => clearInterval(interval)
  }, [])

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
                 (data.executed ? "\n\n✅ Changes applied to CATIA." : (data.error ? `\n\n❌ Error: ${data.error}` : ""))
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: "Sorry, I'm having trouble connecting to the backend." }])
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
        />

        <ChatWindow
          ref={chatWindowRef}
          messages={messages}
          onSendMessage={handleSendMessage}
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
