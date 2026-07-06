import { MagnifyingGlass, Star, Package } from "@phosphor-icons/react"

function formatPrice(price) {
  return `₹${price.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

function ProductCard({ product, onAddToCart }) {
  const inStock = product.stock > 0
  return (
    <div
      id={`product-${product.id}`}
      className="flex flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white transition-shadow hover:shadow-md"
    >
      <img src={product.image_url} alt={product.name} className="aspect-square w-full object-cover" />
      <div className="flex flex-1 flex-col gap-1 p-4">
        <span className="text-xs text-zinc-500">{product.brand}</span>
        <h3 className="line-clamp-2 text-sm font-medium text-zinc-900">{product.name}</h3>
        <div className="mt-1 flex items-center gap-1 text-xs text-zinc-500">
          <Star size={14} weight="fill" className="text-amber-400" />
          {product.rating}
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-base font-semibold text-zinc-900">{formatPrice(product.price)}</span>
          <span className={inStock ? "text-xs text-emerald-600" : "text-xs text-rose-600"}>
            {inStock ? "In stock" : "Out of stock"}
          </span>
        </div>
        <button
          type="button"
          disabled={!inStock}
          onClick={() => onAddToCart(product.id)}
          className="mt-3 rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400"
        >
          Add to cart
        </button>
      </div>
    </div>
  )
}

export default function ProductGrid({
  products,
  categories,
  activeCategory,
  onCategoryChange,
  searchTerm,
  onSearchChange,
  onAddToCart,
}) {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="relative mb-6">
        <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search products..."
          className="w-full rounded-full border border-zinc-200 bg-white py-2.5 pl-10 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
      </div>

      <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
        <button
          type="button"
          onClick={() => onCategoryChange(null)}
          className={`shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition ${
            activeCategory === null ? "bg-indigo-600 text-white" : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
          }`}
        >
          All
        </button>
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onCategoryChange(c)}
            className={`shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition ${
              activeCategory === c ? "bg-indigo-600 text-white" : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {products.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-24 text-zinc-400">
          <Package size={40} />
          <p className="text-sm">No products found</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />
          ))}
        </div>
      )}
    </div>
  )
}
