import { useEffect, useRef, useState } from "react"
import { ChatCircleDots, PaperPlaneRight, X } from "@phosphor-icons/react"
import { CHAT_URL } from "../lib/api"

const TOOL_LABELS = {
  search_products: "Searching products...",
  manage_cart: "Updating your cart...",
  get_order_history: "Checking your orders...",
  get_recommendations: "Finding recommendations...",
}

async function* readSSE(response) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop()
    for (const raw of events) {
      const line = raw.trim()
      if (line.startsWith("data: ")) yield JSON.parse(line.slice(6))
    }
  }
}

export default function ChatWidget({ userId }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [toolLabel, setToolLabel] = useState(null)
  const [streaming, setStreaming] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, toolLabel])

  async function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return
    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "", products: [] }])
    setStreaming(true)

    const response = await fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, message: text }),
    })

    for await (const event of readSSE(response)) {
      if (event.type === "token") {
        setMessages((prev) => {
          const next = [...prev]
          next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + event.data }
          return next
        })
      } else if (event.type === "tool_call") {
        if (event.data.status === "start") {
          setToolLabel(TOOL_LABELS[event.data.name] || "Working...")
        } else {
          setToolLabel(null)
          if (Array.isArray(event.data.result) && event.data.result[0]?.id) {
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              next[next.length - 1] = { ...last, products: [...last.products, ...event.data.result] }
              return next
            })
          }
        }
      } else if (event.type === "done") {
        setStreaming(false)
      }
    }
  }

  function scrollToProduct(id) {
    document.getElementById(`product-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition active:scale-95"
        aria-label="Open chat"
      >
        <ChatCircleDots size={26} weight="fill" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[500px] w-[400px] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-zinc-900">Ask Dukaan</h2>
        <button type="button" onClick={() => setOpen(false)} className="rounded-full p-1 hover:bg-zinc-100" aria-label="Close chat">
          <X size={16} className="text-zinc-500" />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-sm text-zinc-400">Ask me to find products, check your cart, or track an order.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                m.role === "user" ? "bg-indigo-600 text-white" : "bg-zinc-100 text-zinc-800"
              }`}
            >
              {m.content || (m.role === "assistant" && streaming && i === messages.length - 1 ? "..." : "")}
              {m.products?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.products.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => scrollToProduct(p.id)}
                      className="rounded-full border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {toolLabel && (
          <div className="flex justify-start">
            <div className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs italic text-zinc-500">{toolLabel}</div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-zinc-200 p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Type a message..."
          className="flex-1 rounded-full border border-zinc-200 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="button"
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-white disabled:bg-zinc-200"
          aria-label="Send message"
        >
          <PaperPlaneRight size={16} weight="fill" />
        </button>
      </div>
    </div>
  )
}
