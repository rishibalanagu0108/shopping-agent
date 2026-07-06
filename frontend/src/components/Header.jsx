import { useEffect, useRef, useState } from "react"
import { CaretDown, Storefront, ShoppingCartSimple } from "@phosphor-icons/react"

export const USERS = [
  { id: 1, name: "Shyam" },
  { id: 2, name: "Priya" },
  { id: 3, name: "Ravi" },
]

export default function Header({ userId, onUserChange, cartCount, onCartClick }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const activeUser = USERS.find((u) => u.id === userId)

  useEffect(() => {
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener("mousedown", onClickOutside)
    return () => document.removeEventListener("mousedown", onClickOutside)
  }, [])

  return (
    <header className="sticky top-0 z-30 h-16 border-b border-zinc-200 bg-white">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <Storefront size={24} weight="fill" className="text-indigo-600" />
          <span className="text-lg font-bold text-zinc-900">Dukaan</span>
        </div>

        <div className="flex items-center gap-4">
          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="flex items-center gap-2 rounded-full border border-zinc-200 px-3 py-1.5 hover:bg-zinc-50"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                {activeUser.name[0]}
              </span>
              <span className="text-sm font-medium text-zinc-700">{activeUser.name}</span>
              <CaretDown size={14} className="text-zinc-400" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-40 rounded-xl border border-zinc-200 bg-white py-1 shadow-lg">
                {USERS.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => {
                      onUserChange(u.id)
                      setMenuOpen(false)
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50 ${
                      u.id === userId ? "font-semibold text-indigo-700" : "text-zinc-700"
                    }`}
                  >
                    {u.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={onCartClick}
            className="relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-zinc-100"
            aria-label="Open cart"
          >
            <ShoppingCartSimple size={22} className="text-zinc-700" />
            {cartCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[11px] font-semibold text-white">
                {cartCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
