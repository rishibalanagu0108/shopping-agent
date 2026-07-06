const BASE_URL = "http://localhost:8000"

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function qs(params) {
  const entries = Object.entries(params).filter(([, v]) => v != null && v !== "")
  return entries.length ? `?${new URLSearchParams(entries)}` : ""
}

export const api = {
  listProducts: (params = {}) => request(`/api/products${qs(params)}`),
  listCategories: () => request("/api/products/categories"),
  getCart: (userId) => request(`/api/cart/${userId}`),
  addToCart: (userId, productId, quantity = 1) =>
    request(`/api/cart/${userId}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, quantity }),
    }),
  removeFromCart: (userId, productId) =>
    request(`/api/cart/${userId}/remove/${productId}`, { method: "DELETE" }),
  checkout: (userId) => request(`/api/cart/${userId}/checkout`, { method: "POST" }),
}

export const CHAT_URL = `${BASE_URL}/api/agent/chat`
