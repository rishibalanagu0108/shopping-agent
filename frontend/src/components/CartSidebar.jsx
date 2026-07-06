import { Minus, Plus, ShoppingCartSimple, Trash, X } from "@phosphor-icons/react"

function formatPrice(price) {
  return `₹${price.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

export default function CartSidebar({ open, onClose, cart, onQtyChange, onRemove, onCheckout, checkingOut }) {
  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/30 transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-sm flex-col bg-white shadow-xl transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <h2 className="text-base font-semibold text-zinc-900">Your cart</h2>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-zinc-100" aria-label="Close cart">
            <X size={18} className="text-zinc-500" />
          </button>
        </div>

        {cart.items.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-zinc-400">
            <ShoppingCartSimple size={40} />
            <p className="text-sm">Your cart is empty</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {cart.items.map((item) => (
              <div key={item.product_id} className="flex items-center gap-3 border-b border-zinc-100 py-3 last:border-0">
                <div className="flex-1">
                  <p className="line-clamp-1 text-sm font-medium text-zinc-900">{item.name}</p>
                  <p className="text-xs text-zinc-500">{formatPrice(item.price)} each</p>
                </div>
                <div className="flex items-center gap-1.5 rounded-full border border-zinc-200 px-1.5 py-0.5">
                  <button
                    type="button"
                    onClick={() => onQtyChange(item.product_id, item.quantity, -1)}
                    className="rounded-full p-1 hover:bg-zinc-100"
                    aria-label="Decrease quantity"
                  >
                    <Minus size={12} />
                  </button>
                  <span className="w-4 text-center text-xs font-medium">{item.quantity}</span>
                  <button
                    type="button"
                    onClick={() => onQtyChange(item.product_id, item.quantity, 1)}
                    className="rounded-full p-1 hover:bg-zinc-100"
                    aria-label="Increase quantity"
                  >
                    <Plus size={12} />
                  </button>
                </div>
                <span className="w-16 text-right text-sm font-semibold text-zinc-900">
                  {formatPrice(item.subtotal)}
                </span>
                <button
                  type="button"
                  onClick={() => onRemove(item.product_id)}
                  className="rounded-full p-1 text-zinc-400 hover:bg-rose-50 hover:text-rose-600"
                  aria-label="Remove item"
                >
                  <Trash size={16} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="border-t border-zinc-200 px-5 py-4">
          <div className="mb-3 flex items-center justify-between text-sm font-medium text-zinc-700">
            <span>Subtotal</span>
            <span className="text-base font-semibold text-zinc-900">{formatPrice(cart.total)}</span>
          </div>
          <button
            type="button"
            disabled={cart.items.length === 0 || checkingOut}
            onClick={onCheckout}
            className="w-full rounded-full bg-indigo-600 py-2.5 text-sm font-medium text-white transition active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400"
          >
            {checkingOut ? "Placing order..." : "Checkout"}
          </button>
        </div>
      </aside>
    </>
  )
}
