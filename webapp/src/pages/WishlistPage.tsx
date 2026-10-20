import React from 'react';
import { Product } from '../types';
import { ProductCard } from '../components/ProductCard';
import { EmptyState } from '../components/EmptyState';
import { Translations } from '../i18n';

interface WishlistPageProps {
  products: Product[];
  wishlistIds: number[];
  onToggleWishlist: (productId: number) => void;
  onSelectProduct: (product: Product) => void;
  onExplore: () => void;
  t: Translations;
}

export const WishlistPage: React.FC<WishlistPageProps> = ({
  products,
  wishlistIds,
  onToggleWishlist,
  onSelectProduct,
  onExplore,
  t,
}) => {
  const wishlistedProducts = products.filter((p) => wishlistIds.includes(p.id));

  if (wishlistedProducts.length === 0) {
    return (
      <EmptyState
        title={t.emptyWishlist}
        subtitle={t.emptyWishlistSubtitle}
        actionButton={{
          text: t.continueShopping,
          onClick: onExplore,
        }}
      />
    );
  }

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      <div className="py-3 flex items-center justify-between">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <span>❤️</span>
          <span>{t.wishlist}</span>
          <span className="text-xs font-bold text-sakura-rose bg-sakura-blush dark:bg-sakura-darkcardsoft px-2 py-0.5 rounded-full">
            {wishlistedProducts.length} ta
          </span>
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {wishlistedProducts.map((p) => (
          <ProductCard
            key={p.id}
            product={p}
            isWishlisted={true}
            onToggleWishlist={onToggleWishlist}
            onSelect={onSelectProduct}
            soldOutLabel={t.soldOut}
          />
        ))}
      </div>
    </div>
  );
};
