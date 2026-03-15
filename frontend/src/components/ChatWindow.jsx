import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import BOMEditor from './BOMEditor'
import BOMSelectionList from './BOMSelectionList'

const ChatWindow = forwardRef(({ messages, onSendMessage, onUpdateBomMessage, onBomExport }, ref) => {
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

    useEffect(() => {
        scrollToBottom()
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
        <section className="flex-1 flex flex-col min-w-0 bg-background">
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'} animate-in fade-in slide-in-from-bottom-2 duration-300`}
                    >
                        <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                            {msg.content}
                        </div>

                        {msg.bomEditor && (
                            <BOMEditor
                                items={msg.bomEditor.items}
                                onItemsChange={(items) => onUpdateBomMessage?.(i, { ...msg.bomEditor, items })}
                                onExport={(items) => onBomExport?.(i, items)}
                                disabled={msg.bomEditor.exporting}
                            />
                        )}
                        
                        {msg.interactive && msg.interactive.type === 'bom-selector' && (
                            <BOMSelectionList
                                items={msg.interactive.items}
                                onCalculationComplete={(results) => {
                                    onUpdateBomMessage?.(i, {
                                        items: results,
                                        exporting: false
                                    })
                                }}
                            />
                        )}

                        {msg.interactive && msg.interactive.type === 'choice' && (
                            <div className="mt-4 flex flex-wrap gap-2 pt-4 border-t border-white/5">
                                {msg.interactive.options.map((opt) => (
                                    <button
                                        key={opt.id}
                                        onClick={() => onSendMessage(opt.value || opt.label)}
                                        className={`text-xs px-3 py-1.5 rounded-lg border transition-all active:scale-95 ${
                                            opt.primary 
                                            ? 'bg-white text-black border-white hover:bg-neutral-200' 
                                            : 'bg-transparent text-white/70 border-white/10 hover:border-white/30 hover:text-white'
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

            <div className="p-6 border-t border-white/5">
                <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask the copilot to modify the CATIA model..."
                        className="w-full bg-secondary/50 border border-white/10 rounded-2xl py-4 pl-4 pr-14 focus:outline-none focus:ring-1 focus:ring-white/20 resize-none h-14 min-h-[56px] text-sm overflow-hidden placeholder:text-muted-foreground/50 transition-all focus:bg-secondary/70"
                        rows={1}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim()}
                        className="absolute right-2 top-2 p-2 rounded-xl bg-white text-black hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
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
