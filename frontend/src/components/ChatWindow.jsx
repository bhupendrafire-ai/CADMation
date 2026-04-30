import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import BOMEditor from './BOMEditor'
import BOMSelectionList from './BOMSelectionList'

const ChatWindow = forwardRef(({ messages, activeDoc, onSendMessage, onUpdateBomMessage, onBomExport, onInteractiveAction, onMeasurementAction, onBomSelectionComplete, onBomDraftUpdate, isEmbedded }, ref) => {
    const [input, setInput] = useState('')
    const messagesEndRef = useRef(null)
    const textareaRef = useRef(null)

    useImperativeHandle(ref, () => ({
        insertText: (text) => {
            const textarea = textareaRef.current
            if (!textarea) return

            const start = textarea.selectionStart
            const end = textarea.selectionEnd
            const value = textarea.value

            const newValue = value.substring(0, start) + text + value.substring(end)
            setInput(newValue)

            // Refocus and set cursor after the inserted text
            setTimeout(() => {
                textarea.focus()
                const newPos = start + text.length
                textarea.setSelectionRange(newPos, newPos)
            }, 0)
        }
    }))

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    const prevMessagesLength = useRef(messages.length)
    useEffect(() => {
        if (messages.length > prevMessagesLength.current) {
            scrollToBottom()
        }
        prevMessagesLength.current = messages.length
    }, [messages])

    const handleSubmit = (e) => {
        e.preventDefault()
        if (!input.trim()) return
        onSendMessage(input)
        setInput('')
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            handleSubmit(e)
        }
    }

    return (
        <section className="flex-1 flex flex-col min-w-0 bg-zen-bg">
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'} animate-in`}
                    >
                        <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                            {msg.content}
                        </div>

                        {msg.bomEditor && (
                            <div className={isEmbedded ? "mt-3 rounded-xl overflow-hidden border border-zen-border bg-zen-surface-alt" : ""}>
                                {isEmbedded ? (
                                    <div className="p-3 flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <svg className="w-4 h-4 text-zen-info" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                                            <span className="text-[11px] font-bold text-zen-text-dim">{msg.bomEditor.items?.length || 0} items in BOM</span>
                                        </div>
                                        <span className="text-[9px] text-zen-text-muted uppercase tracking-widest font-mono">Synced to Workspace</span>
                                    </div>
                                ) : (
                                    <BOMEditor
                                        items={msg.bomEditor.items}
                                        projectName={activeDoc}
                                        onItemsChange={(items) => onUpdateBomMessage?.(i, { ...msg.bomEditor, items })}
                                        onExport={(items) => onBomExport?.(i, items)}
                                        disabled={msg.bomEditor.exporting}
                                    />
                                )}
                            </div>
                        )}
                        
                        {msg.interactive && msg.interactive.type === 'bom-selector' && (
                            <div className={isEmbedded ? "mt-3 rounded-xl overflow-hidden border border-zen-border bg-zen-surface-alt" : ""}>
                                {isEmbedded ? (
                                    <div className="p-4 text-center">
                                         <p className="text-[11px] text-zen-text-dim mb-3">BOM selection required for {msg.interactive.items?.length || 0} parts.</p>
                                         <p className="text-[10px] font-bold text-zen-info uppercase tracking-widest">Active in BOM Workspace</p>
                                    </div>
                                ) : (
                                    <BOMSelectionList
                                        items={msg.interactive.items}
                                        projectName={activeDoc}
                                        bomOptions={msg.interactive.bomOptions}
                                        onAction={onMeasurementAction}
                                        onUpdate={(items) => onBomDraftUpdate?.(i, items)}
                                        onCalculationComplete={(payload) => {
                                            onBomSelectionComplete?.(i, payload)
                                        }}
                                        onPartialExport={(items) => onBomExport?.(i, items)}
                                    />
                                )}
                            </div>
                        )}

                        {msg.interactive && msg.interactive.type === 'choice' && (
                            <div className="mt-4 flex flex-wrap gap-2 pt-4 border-t border-zen-border">
                                {msg.interactive.options.map((opt) => (
                                    <button
                                        key={opt.id}
                                        onClick={() => {
                                            if (opt.action) {
                                                onInteractiveAction?.(i, opt.action)
                                                return
                                            }
                                            onSendMessage(opt.value || opt.label)
                                        }}
                                        className={`text-xs px-4 py-2 rounded-full border transition-all active:scale-95 ${
                                            opt.primary 
                                            ? 'bg-zen-primary text-white border-zen-primary hover:scale-105' 
                                            : 'bg-zen-surface text-zen-text-dim border-zen-border hover:border-zen-text-muted hover:text-zen-text-main'
                                        }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <div className={`p-6 border-t border-zen-border ${isEmbedded ? 'bg-zen-surface-alt' : ''}`}>
                <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={isEmbedded ? "Ask Copilot..." : "Ask the copilot to modify the CATIA model..."}
                        className={`w-full bg-zen-surface border border-zen-border rounded-2xl py-4 pl-4 pr-14 focus:outline-none focus:ring-1 focus:ring-zen-text-muted resize-none h-14 min-h-[56px] text-sm overflow-hidden placeholder:text-zen-text-muted transition-all focus:border-zen-border-strong text-zen-text-main ${isEmbedded ? 'text-xs' : ''}`}
                        rows={1}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim()}
                        className="absolute right-2 top-2 p-2 rounded-full bg-zen-primary text-white hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed transition-all active:scale-95"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </form>
            </div>
        </section>
    )
})

export default ChatWindow
