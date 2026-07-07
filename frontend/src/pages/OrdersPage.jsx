import { useEffect, useState } from "react"
import { Receipt } from "@phosphor-icons/react"
import { api } from "../lib/api"

function formatPrice(value) {
  return `₹${value.toFixed(2)}`
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
}

export default function OrdersPage({ userId }) {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getOrders(userId).then((data) => {
      setOrders(data)
      setLoading(false)
    })
  }, [userId])

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="mb-6 text-xl font-semibold text-zinc-900">Your orders</h1>

      {loading ? (
        <p className="text-sm text-zinc-500">Loading...</p>
      ) : orders.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-zinc-300 py-16 text-zinc-400">
          <Receipt size={40} />
          <p className="text-sm">No orders yet</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {orders.map((order) => (
            <div key={order.order_id} className="rounded-xl border border-zinc-200 bg-white p-4">
              <div className="mb-3 flex items-center justify-between border-b border-zinc-100 pb-3">
                <div>
                  <p className="text-sm font-semibold text-zinc-900">Order #{order.order_id}</p>
                  <p className="text-xs text-zinc-500">{formatDate(order.created_at)}</p>
                </div>
                <span className="text-sm font-semibold text-zinc-900">{formatPrice(order.total)}</span>
              </div>
              <ul className="flex flex-col gap-1.5">
                {order.items.map((item, i) => (
                  <li key={i} className="flex justify-between text-sm text-zinc-600">
                    <span>
                      {item.quantity}x {item.name}
                    </span>
                    <span>{formatPrice(item.price * item.quantity)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
