import React, { useEffect, useState } from 'react';
import { Trash2, Plus, Minus, Send, Copy, Check, ShoppingBag, ArrowRight } from 'lucide-react';
import { CartSummary, Order, ShopSettings } from '../types';
import { formatPrice, getMediaUrl } from '../utils/format';
import { getTelegramWebApp, haptic, openTelegramLink } from '../utils/telegram';
import { triggerPetalBurst } from '../components/PetalBurst';
import { EmptyState } from '../components/EmptyState';
import { Translations } from '../i18n';

interface BagPageProps {
  cart: CartSummary | null;
  settings: ShopSettings;
  onUpdateQty: (itemId: number, newQty: number) => void;
  onRemoveItem: (itemId: number) => void;
  onClearCart: () => void;
  onOrderSuccess: (order: Order) => void;
  onContinueShopping: () => void;
  t: Translations;
  initData: string;
}

export const BagPage: React.FC<BagPageProps> = ({
  cart,
  settings,
  onUpdateQty,
  onRemoveItem,
  onClearCart,
  onOrderSuccess,
  onContinueShopping,
  t,
  initData,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completedOrder, setCompletedOrder] = useState<Order | null>(null);
  const [copied, setCopied] = useState(false);

  const items = cart?.items || [];
  const hasItems = items.length > 0;

  // Handle Telegram MainButton
  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg?.MainButton) return;

    if (hasItems && !completedOrder) {
      tg.MainButton.setText(t.checkoutButton);
      tg.MainButton.show();
      tg.MainButton.enable();

      const handleMainButtonClick = () => {
        handleCheckout();
      };

      tg.MainButton.onClick(handleMainButtonClick);
      return () => {
        tg.MainButton.offClick(handleMainButtonClick);
        tg.MainButton.hide();
      };
    } else {
      tg.MainButton.hide();
    }
  }, [hasItems, completedOrder, t.checkoutButton]);

  const handleCheckout = async () => {
    if (!hasItems || isSubmitting) return;

    setIsSubmitting(true);
    const tg = getTelegramWebApp();
    tg?.MainButton?.showProgress();
    haptic.impact('heavy');

    try {
      const resp = await fetch('/api/orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({}),
      });

      if (!resp.ok) {
        throw new Error('Order creation failed');
      }

      const orderData: Order = await resp.json();
      setCompletedOrder(orderData);
      triggerPetalBurst(0.5, 0.4);
      haptic.notification('success');
      onOrderSuccess(orderData);
    } catch (err) {
      console.error(err);
      haptic.notification('error');
      alert("Buyurtma berishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.");
    } finally {
      setIsSubmitting(false);
      tg?.MainButton?.hideProgress();
      tg?.MainButton?.hide();
    }
  };

  const handleCopyCodeBlock = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    haptic.notification('success');
    setTimeout(() => setCopied(false), 2500);
  };

  // SUCCESS VIEW AFTER CHECKOUT
  if (completedOrder) {
    const contact = (settings.contact_username || 'fkhrdnvvvva').replace('@', '');

    const copyableSummary =
      `🌸 Sakura shop — Buyurtma #${completedOrder.id}\n` +
      `Mijoz: ${completedOrder.customer_name}\n\n` +
      completedOrder.items_snapshot
        .map(
          (it, i) =>
            `${i + 1}. ${it.title} ${it.size ? `(${it.size})` : ''} ${it.color ? `(${it.color})` : ''} — ${it.qty} dona (${formatPrice(it.price * it.qty)})`
        )
        .join('\n') +
      `\n\nJami: ${formatPrice(completedOrder.total)}\n` +
      (completedOrder.estimated_cargo > 0
        ? `📦 Taxminiy kargo: ${formatPrice(completedOrder.estimated_cargo)}\n`
        : '');

    return (
      <div className="p-4 pb-28 max-w-md mx-auto text-center animate-scale-in">
        <div className="w-20 h-20 mx-auto my-3 rounded-full bg-sakura-blush dark:bg-sakura-darkcardsoft flex items-center justify-center text-4xl shadow-sakura">
          🌸
        </div>
        <h2 className="text-xl font-extrabold text-sakura-darkrose dark:text-sakura-pink">
          {t.orderSuccessTitle}
        </h2>
        <p className="text-xs text-sakura-plum/80 dark:text-sakura-blush/80 mt-1.5 px-4">
          {t.orderSuccessSubtitle}
        </p>

        {/* Copyable Summary Card */}
        <div className="mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm text-left">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-sakura-rose">
              Buyurtma #{completedOrder.id}
            </span>
            <button
              onClick={() => handleCopyCodeBlock(copyableSummary)}
              className="flex items-center gap-1 px-3 py-1 rounded-xl bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-rose font-bold text-xs shadow-xs active:scale-95 transition-transform"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? t.copied : t.copySummary}</span>
            </button>
          </div>

          <pre className="p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkbg text-[11px] font-mono text-sakura-plum dark:text-sakura-blush overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
            {copyableSummary}
          </pre>
        </div>

        {/* Message Admin Button */}
        <div className="mt-4 flex flex-col gap-2.5">
          <button
            onClick={() => {
              const url = `https://t.me/${contact}?text=${encodeURIComponent(copyableSummary)}`;
              openTelegramLink(url);
            }}
            className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black text-sm flex items-center justify-center gap-2 shadow-sakura active:scale-95 transition-transform"
          >
            <Send className="w-4 h-4" />
            <span>{t.messageAdminButton}</span>
          </button>

          <button
            onClick={onContinueShopping}
            className="w-full py-3 px-4 rounded-2xl bg-white/80 dark:bg-sakura-darkcard/80 text-sakura-plum dark:text-white font-bold text-xs flex items-center justify-center gap-1.5 border border-sakura-pink/30 active:scale-95 transition-transform"
          >
            <span>{t.continueShopping}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // EMPTY BAG STATE
  if (!hasItems) {
    return (
      <EmptyState
        title={t.emptyBag}
        subtitle={t.emptyBagSubtitle}
        actionButton={{
          text: t.continueShopping,
          onClick: onContinueShopping,
        }}
      />
    );
  }

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      {/* Title & Clear Cart */}
      <div className="py-3 flex items-center justify-between">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <span>🛍️</span>
          <span>{t.bag}</span>
          <span className="text-xs font-bold text-sakura-rose bg-sakura-blush dark:bg-sakura-darkcardsoft px-2 py-0.5 rounded-full">
            {cart?.total_items} ta
          </span>
        </h2>
        <button
          onClick={onClearCart}
          className="text-xs font-bold text-sakura-plum/60 hover:text-sakura-rose flex items-center gap-1"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Tozalash</span>
        </button>
      </div>

      {/* Cart Items List */}
      <div className="flex flex-col gap-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 p-3 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm"
          >
            {/* Thumbnail */}
            <div className="w-16 h-16 rounded-2xl overflow-hidden shrink-0 bg-sakura-blush">
              <img
                src={getMediaUrl(item.product_photo)}
                alt={item.product_title}
                className="w-full h-full object-cover"
              />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <h4 className="text-xs sm:text-sm font-bold text-sakura-plum dark:text-white line-clamp-1">
                {item.product_title}
              </h4>
              <div className="flex items-center gap-2 text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70 mt-0.5">
                {item.size && <span>O'lcham: {item.size}</span>}
                {item.color && <span>Rang: {item.color}</span>}
              </div>
              <span className="text-xs font-black text-sakura-rose dark:text-sakura-pink block mt-1">
                {formatPrice(item.item_total)}
              </span>
            </div>

            {/* Qty +/- Controls */}
            <div className="flex items-center gap-1.5 bg-sakura-cream dark:bg-sakura-darkcardsoft p-1 rounded-2xl border border-sakura-pink/30">
              <button
                onClick={() => {
                  haptic.selection();
                  if (item.qty > 1) {
                    onUpdateQty(item.id, item.qty - 1);
                  } else {
                    onRemoveItem(item.id);
                  }
                }}
                className="p-1 rounded-xl hover:bg-sakura-pink/20 active:scale-90"
              >
                {item.qty === 1 ? <Trash2 className="w-3.5 h-3.5 text-rose-500" /> : <Minus className="w-3.5 h-3.5" />}
              </button>

              <span className="text-xs font-extrabold w-5 text-center">{item.qty}</span>

              <button
                onClick={() => {
                  haptic.selection();
                  onUpdateQty(item.id, item.qty + 1);
                }}
                className="p-1 rounded-xl hover:bg-sakura-pink/20 active:scale-90"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Cart Summary Card */}
      <div className="mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm">
        <div className="flex justify-between text-xs py-1">
          <span className="text-sakura-plum/70 dark:text-sakura-blush/70">{t.subtotal}:</span>
          <span className="font-extrabold">{cart?.formatted_subtotal}</span>
        </div>
        {cart?.estimated_cargo ? (
          <div className="flex justify-between text-xs py-1">
            <span className="text-sakura-plum/70 dark:text-sakura-blush/70">{t.estimatedCargo}:</span>
            <span className="font-extrabold">{cart?.formatted_estimated_cargo}</span>
          </div>
        ) : null}
        <div className="my-2 border-t border-sakura-pink/20" />
        <div className="flex justify-between text-sm sm:text-base py-1">
          <span className="font-black text-sakura-plum dark:text-white">{t.grandTotal}:</span>
          <span className="font-black text-sakura-rose dark:text-sakura-pink">
            {cart?.formatted_grand_total}
          </span>
        </div>
        <p className="text-[10px] text-sakura-plum/60 dark:text-sakura-blush/60 mt-1 italic text-center">
          * {settings.payment_terms || "100% oldindan to'lov"} sharti bilan
        </p>
      </div>

      {/* Fallback In-Page Checkout Button */}
      <div className="mt-4">
        <button
          onClick={handleCheckout}
          disabled={isSubmitting}
          className="w-full py-4 px-4 rounded-3xl bg-gradient-to-r from-sakura-pink via-sakura-rose to-sakura-darkrose text-white font-black text-sm sm:text-base flex items-center justify-center gap-2 shadow-sakura hover:opacity-95 active:scale-95 transition-all"
        >
          <ShoppingBag className="w-5 h-5" />
          <span>{isSubmitting ? "Buyurtma yuborilmoqda..." : t.checkoutButton}</span>
        </button>
      </div>
    </div>
  );
};
