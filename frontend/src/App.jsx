import { useEffect, useState } from "react"
import { CheckCircle } from "@phosphor-icons/react"
import Header from "./components/Header"
import ProductGrid from "./components/ProductGrid"
import CartSidebar from "./components/CartSidebar"
import ChatWidget from "./components/ChatWidget"
import { api } from "./lib/api"

const EMPTY_CART = { items: [], total: 0 }

function App() {
  const [userId, setUserId] = useState(1)
  const [categories, setCategories] = useState([])
  const [activeCategory, setActiveCategory] = useState(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [products, setProducts] = useState([])
  const [cart, setCart] = useState(EMPTY_CART)
  const [cartOpen, setCartOpen] = useState(false)
  const [checkingOut, setCheckingOut] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    api.listCategories().then(setCategories)
  }, [])

  useEffect(() => {
    api.getCart(userId).then(setCart)
  }, [userId])

  useEffect(() => {
    const timer = setTimeout(() => {
      api.listProducts({ category: activeCategory, search: searchTerm }).then(setProducts)
    }, 250)
    return () => clearTimeout(timer)
  }, [activeCategory, searchTerm])

  function showToast(message) {
    setToast(message)
    setTimeout(() => setToast(null), 2500)
  }

  function refreshCart() {
    api.getCart(userId).then(setCart)
  }

  function handleAddToCart(productId) {
    api.addToCart(userId, productId, 1).then(refreshCart)
  }

  function handleQtyChange(productId, currentQty, delta) {
    const request = currentQty + delta <= 0 ? api.removeFromCart(userId, productId) : api.addToCart(userId, productId, delta)
    request.then(refreshCart)
  }

  function handleCheckout() {
    setCheckingOut(true)
    api
      .checkout(userId)
      .then(() => {
        refreshCart()
        showToast("Order placed!")
        setCartOpen(false)
      })
      .finally(() => setCheckingOut(false))
  }

  const cartCount = cart.items.reduce((sum, item) => sum + item.quantity, 0)

  return (
    <div className="min-h-screen bg-zinc-50">
      <Header
        userId={userId}
        onUserChange={setUserId}
        cartCount={cartCount}
        onCartClick={() => setCartOpen(true)}
      />

      <ProductGrid
        products={products}
        categories={categories}
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        onAddToCart={handleAddToCart}
      />

      <CartSidebar
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        cart={cart}
        onQtyChange={handleQtyChange}
        onRemove={(productId) => api.removeFromCart(userId, productId).then(refreshCart)}
        onCheckout={handleCheckout}
        checkingOut={checkingOut}
      />

      <ChatWidget key={userId} userId={userId} onCartChange={refreshCart} />

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-2 rounded-full bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          <CheckCircle size={18} weight="fill" className="text-emerald-400" />
          {toast}
        </div>
      )}
    </div>
  )
}

export default App
