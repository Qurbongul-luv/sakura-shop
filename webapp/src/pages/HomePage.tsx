import React, { useState, useEffect } from 'react';
import { Product, Category } from '../types';
import { CategoryChips } from '../components/CategoryChips';
import { HeroProduct } from '../components/HeroProduct';
import { Carousel } from '../components/Carousel';
import { ProductCard } from '../components/ProductCard';
import { EmptyState } from '../components/EmptyState';
import { Translations } from '../i18n';

interface HomePageProps {
  products: Product[];
  categories: Category[];
  heroProduct: Product | null;
  wishlistIds: number[];
  onToggleWishlist: (productId: number) => void;
  onSelectProduct: (product: Product) => void;
  searchQuery: string;
  selectedCategory: string | null;
  onSelectCategory: (slug: string | null) => void;
  t: Translations;
  loading: boolean;
}

export const HomePage: React.FC<HomePageProps> = ({
  products,
  categories,
  heroProduct,
  wishlistIds,
  onToggleWishlist,
  onSelectProduct,
  searchQuery,
  selectedCategory,
  onSelectCategory,
  t,
  loading,
}) => {
  // Filter products by category and search
  const filteredProducts = products.filter((p) => {
    const matchesCat = selectedCategory ? p.category.toLowerCase() === selectedCategory.toLowerCase() : true;
    const matchesSearch = searchQuery
      ? p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.category.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    return matchesCat && matchesSearch;
  });

  const newProducts = products.filter((p) => p.is_new && p.in_stock);
  const hitProducts = products.filter((p) => p.is_hit && p.in_stock);

  return (
    <div className="pb-24">
      {/* Category Hashtag Chips */}
      <CategoryChips
        categories={categories}
        selectedCategory={selectedCategory}
        onSelectCategory={onSelectCategory}
        allLabel={t.allCategories}
      />

      {/* Hero "Product of the day" (Only on default view) */}
      {!searchQuery && !selectedCategory && heroProduct && (
        <HeroProduct
          product={heroProduct}
          onSelect={onSelectProduct}
          titleLabel={t.productOfTheDay}
        />
      )}

      {/* New Arrivals Carousel (Only on default view) */}
      {!searchQuery && !selectedCategory && newProducts.length > 0 && (
        <Carousel
          title={t.newArrivals}
          products={newProducts}
          wishlistIds={wishlistIds}
          onToggleWishlist={onToggleWishlist}
          onSelect={onSelectProduct}
          soldOutLabel={t.soldOut}
        />
      )}

      {/* Hit Products Carousel (Only on default view) */}
      {!searchQuery && !selectedCategory && hitProducts.length > 0 && (
        <Carousel
          title={t.hitProducts}
          products={hitProducts}
          wishlistIds={wishlistIds}
          onToggleWishlist={onToggleWishlist}
          onSelect={onSelectProduct}
          soldOutLabel={t.soldOut}
        />
      )}

      {/* Main Catalog Header */}
      <div className="px-4 mt-4 mb-2.5 flex items-center justify-between">
        <h3 className="text-base font-extrabold text-sakura-plum dark:text-white flex items-center gap-1.5">
          <span>🌸</span>
          <span>
            {selectedCategory
              ? `#${selectedCategory}`
              : searchQuery
              ? `Qidiruv natijalari: "${searchQuery}"`
              : 'Barcha kiyimlar & aksessuarlar'}
          </span>
        </h3>
        <span className="text-xs font-semibold text-sakura-plum/60 dark:text-sakura-blush/60">
          {filteredProducts.length} ta
        </span>
      </div>

      {/* Loading Skeletons */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3 px-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="rounded-3xl bg-white/70 dark:bg-sakura-darkcard p-3 animate-pulse shadow-sm">
              <div className="w-full aspect-square rounded-2xl bg-sakura-blush/50 dark:bg-sakura-darkcardsoft mb-2" />
              <div className="h-4 bg-sakura-blush/60 dark:bg-sakura-darkcardsoft rounded w-3/4 mb-1.5" />
              <div className="h-4 bg-sakura-blush/40 dark:bg-sakura-darkcardsoft rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : filteredProducts.length === 0 ? (
        <EmptyState
          title="Hech narsa topilmadi 🌸"
          subtitle="Boshqa qidiruv so'zini sinab ko'ring yoki boshqa kategoriyani tanlang!"
          actionButton={{
            text: "Barcha mahsulotlar",
            onClick: () => {
              onSelectCategory(null);
            },
          }}
        />
      ) : (
        /* 2-Column Product Grid */
        <div className="grid grid-cols-2 gap-3 px-4">
          {filteredProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              isWishlisted={wishlistIds.includes(product.id)}
              onToggleWishlist={onToggleWishlist}
              onSelect={onSelectProduct}
              soldOutLabel={t.soldOut}
            />
          ))}
        </div>
      )}
    </div>
  );
};
